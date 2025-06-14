"""
This module provides functionality for handling multi-turn conversation requests 
in a FastAPI application. It includes utilities for sanitizing messages, 
forwarding requests to other services using Consul service discovery, and 
processing responses.
Functions:
    sanitize_messages(messages):
        Sanitizes a list of messages by removing HTML details tags and stripping 
        whitespace. Logs an error for any non-dictionary messages encountered.
    post_to_service(service_name, endpoint, payload, error_prefix, timeout=60):
        Sends a POST request to a specified service endpoint using Consul service 
        discovery. Handles errors and raises HTTP exceptions for service 
        unavailability, connection failures, or HTTP errors.
Routes:
    @router.post("/api/multiturn", response_model=ProxyResponse):
        endpoint (/api/multiturn). Acts as a proxy with no additional 
        processing. Handles intents detection, retrieves the current mode, 
        queries memory, sanitizes messages, and processes the proxy response.
"""
import shared.consul

from shared.models.proxy import MultiTurnRequest, ProxyResponse  # Removed ChatMessage import
from shared.models.memory import MemoryListQuery
from shared.models.summary import Summary
from shared.models.notification import LastSeen

from app.memory.get import list_memory
from app.util import get_admin_user_id, post_to_service, get_user_alias, sanitize_messages
from app.last_seen import update_last_seen
from app.divoom.update import update_divoom

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import json
import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/shared/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/api/multiturn", response_model=ProxyResponse)
async def outgoing_multiturn_message(message: MultiTurnRequest) -> ProxyResponse:
    """
    This function needs a big rework.

    For one, while the way we're loading brainlets looks good, there are some brainlets
    that I want to run after we get the assistant response - like picking an emoji for the divoom.

    """
    logger.debug(f"brain: /api/multiturn Request:")

    # Memories only apply to ollama requests - we should not be sending them to openai requests.
    memories = []
    if message.provider == "ollama":
        # get a list of memories
        memory_query = MemoryListQuery(component="proxy", limit=100, mode=message.model)
        memories = await list_memory(memory_query)
    
        # sanitize proxy messages
        message.messages = sanitize_messages(message.messages)

    # get username
    message.user_id = await get_admin_user_id()
    username = await get_user_alias(message.user_id)
    platform = message.platform or "api"

    # get a list of the last 4 summaries - this returns a formatted string
    from app.notification.util import get_recent_summaries
    summaries = await get_recent_summaries(message.user_id, limit=4)
    if not summaries:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )
    # summaries is already a formatted string, no need to re-parse or join

    # Build new MultiTurnRequest with updated fields
    with open('/app/app/tools.json') as f:
        tools = json.load(f)

    updated_request = message.copy(update={
        "memories": [m.model_dump() for m in memories],
        "messages": message.messages,
        "username": username,
        "summaries": summaries,
        "platform": platform,
        "tools": tools,  # <-- This line is needed!
    })

    # --- Send last 4 messages to ledger as RawUserMessage ---
    from app.notification.util import sync_with_ledger
    try:
        platform_msg_id = None
        last_msgs = updated_request.messages[-4:]
        sync_snapshot = [
            {
                "user_id": message.user_id,
                "platform": platform,
                "platform_msg_id": platform_msg_id,
                "role": m.get("role"),
                "content": m.get("content"),
                "model": message.model if hasattr(message, 'model') else None,
                # Only include the first tool_call dict if tool_calls is a non-empty list, else dict, else None
                "tool_calls": m.get("tool_calls")[0] if isinstance(m.get("tool_calls"), list) and m.get("tool_calls") else m.get("tool_calls") if isinstance(m.get("tool_calls"), dict) else None,
                "function_call": m.get("function_call"),
            }
            for m in last_msgs
        ]
        ledger_buffer = await sync_with_ledger(
            user_id=message.user_id,
            platform=platform,
            snapshot=sync_snapshot,
            error_prefix="Error forwarding to ledger service",
            logger=logger
        )
        # Use dicts for messages, not ChatMessage, and preserve tool_calls/function_call/tool_call_id fields
        updated_request = updated_request.copy(update={
            "messages": [
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    **({"tool_calls": msg["tool_calls"]} if msg.get("tool_calls") is not None else {}),
                    **({"function_call": msg["function_call"]} if msg.get("function_call") is not None else {}),
                    **({"tool_call_id": msg["tool_call_id"]} if msg.get("tool_call_id") is not None else {}),
                }
                for msg in ledger_buffer
            ]
        })
    except Exception as e:
        logger.error(f"Error sending messages to ledger sync endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync messages with ledger service."
        )
    # Run the brainlets!
    # Load brainlets config and import brainlets
    brainlets_config = _config.get('brainlets', [])
    import app.brainlets

    # Topological sort to respect depends_on
    def topo_sort_brainlets(brainlets):
        from collections import defaultdict, deque
        name_to_brainlet = {b['name']: b for b in brainlets}
        graph = defaultdict(list)
        indegree = defaultdict(int)
        for b in brainlets:
            for dep in b.get('depends_on', []):
                graph[dep].append(b['name'])
                indegree[b['name']] += 1
            if b['name'] not in indegree:
                indegree[b['name']] = 0
        # Kahn's algorithm
        queue = deque([name for name, deg in indegree.items() if deg == 0])
        sorted_names = []
        while queue:
            name = queue.popleft()
            sorted_names.append(name)
            for neighbor in graph[name]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)
        # Only return brainlets that are in the config and in the sorted order
        return [name_to_brainlet[name] for name in sorted_names if name in name_to_brainlet]

    brainlets_sorted = topo_sort_brainlets(brainlets_config)
    # Filter for pre-execution brainlets only
    pre_brainlets = [b for b in brainlets_sorted if b.get('execution_stage') == 'pre']
    brainlets_output = {}
    for brainlet in pre_brainlets:
        modes = brainlet.get('modes', [])
        if message.model in modes:
            logger.debug(f"Running brainlet: {brainlet['name']} for mode: {message.model}")
            brainlet_name = brainlet['name']
            brainlet_func = getattr(app.brainlets, brainlet_name, None)
            if brainlet_func:
                logger.debug(f"Found brainlet function: {brainlet_func.__name__}")
                brainlet_result = await brainlet_func(brainlets_output, updated_request)
                logger.debug(f"brainlet_result type: {type(brainlet_result)}, value: {brainlet_result}")
                if brainlet_result and isinstance(brainlet_result, dict):
                    logger.debug(f"Brainlet {brainlet_name} returned: {brainlet_result}")
                    # Sync any lists of message dicts inside the dict
                    for val in brainlet_result.values():
                        if isinstance(val, list):
                            for msg_dict in val:
                                logger.debug(f"Processing brainlet message from dict value: {msg_dict}")
                                if isinstance(msg_dict, dict) and msg_dict.get("role") in ("assistant", "tool"):
                                    sync_snapshot = [
                                        {
                                            "user_id": message.user_id,
                                            "platform": platform,
                                            "platform_msg_id": None,
                                            "role": msg_dict.get("role"),
                                            "content": msg_dict.get("content"),
                                            "model": message.model if hasattr(message, 'model') else None,
                                            "tool_calls": msg_dict.get("tool_calls"),
                                            "function_call": msg_dict.get("function_call"),
                                            "tool_call_id": msg_dict.get("tool_call_id"),
                                        }
                                    ]
                                    try:
                                        logger.debug(f"Syncing brainlet message to ledger: {sync_snapshot}")
                                        await sync_with_ledger(
                                            user_id=message.user_id,
                                            platform=platform,
                                            snapshot=sync_snapshot,
                                            error_prefix=f"Error forwarding brainlet ({brainlet_name}) message to ledger",
                                            logger=logger
                                        )
                                        logger.debug("Ledger sync successful.")
                                    except Exception as e:
                                        logger.error(f"Ledger sync failed for brainlet {brainlet_name}: {e}")
                brainlets_output[brainlet_name] = brainlet_result
            elif brainlet_result and isinstance(brainlet_result, list):
                for msg_dict in brainlet_result:
                    logger.debug(f"Processing brainlet message: {msg_dict}")
                    if isinstance(msg_dict, dict) and msg_dict.get("role") in ("assistant", "tool"):
                        sync_snapshot = [
                            {
                                "user_id": message.user_id,
                                "platform": platform,
                                "platform_msg_id": None,
                                "role": msg_dict.get("role"),
                                "content": msg_dict.get("content"),
                                "model": message.model if hasattr(message, 'model') else None,
                                "tool_calls": msg_dict.get("tool_calls"),
                                "function_call": msg_dict.get("function_call"),
                                "tool_call_id": msg_dict.get("tool_call_id"),
                            }
                        ]
                        try:
                            logger.debug(f"Syncing brainlet message to ledger: {sync_snapshot}")
                            await sync_with_ledger(
                                user_id=message.user_id,
                                platform=platform,
                                snapshot=sync_snapshot,
                                error_prefix=f"Error forwarding brainlet ({brainlet_name}) message to ledger",
                                logger=logger
                            )
                            logger.debug("Ledger sync successful.")
                        except Exception as e:
                            logger.error(f"Ledger sync failed for brainlet {brainlet_name}: {e}")
                brainlets_output[brainlet_name] = brainlet_result

    # Merge brainlets_output lists into updated_request.messages
    for v in brainlets_output.values():
        if isinstance(v, list):
            updated_request.messages.extend(v)
        elif isinstance(v, dict):
            # If the dict contains a list under any key, extend messages with it
            for val in v.values():
                if isinstance(val, list):
                    updated_request.messages.extend(val)

    # send the payload to the proxy service and handle tool call loop
    from app.tools import TOOL_FUNCTIONS
    import json as _json
    final_response = None
    message_buffer = updated_request.messages
    tool_loop_count = 0
    MAX_TOOL_LOOPS = 10
    while tool_loop_count < MAX_TOOL_LOOPS:
        # 1. Send to proxy
        response = await post_to_service(
            'proxy', '/api/multiturn', updated_request.model_dump(),
            error_prefix="Error forwarding to proxy service"
        )
        try:
            json_response = response.json()
            proxy_response = ProxyResponse.model_validate(json_response)
        except Exception as e:
            logger.debug(f"Error parsing response from proxy service: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse response from proxy service: {e}"
            )

        # 2. Sync assistant/tool call message to ledger
        sync_snapshot = [{
            "user_id": message.user_id,
            "platform": platform,
            "platform_msg_id": None,
            "role": "assistant",
            "content": proxy_response.response,
            "model": message.model if hasattr(message, 'model') else None,
            # Only include the first tool_call dict if tool_calls is a non-empty list
            "tool_calls": proxy_response.tool_calls[0] if isinstance(proxy_response.tool_calls, list) and proxy_response.tool_calls else None,
            "function_call": getattr(proxy_response, 'function_call', None),
        }]
        await sync_with_ledger(
            user_id=message.user_id,
            platform=platform,
            snapshot=sync_snapshot,
            error_prefix="Error forwarding to ledger service (proxy_response)",
            logger=logger
        )

        # 3. If tool call, execute tool and loop
        tool_calls = getattr(proxy_response, 'tool_calls', None)
        if tool_calls:
            for tool_call in tool_calls:
                if tool_call.get('type') == 'function':
                    fn = tool_call['function']['name']
                    args = tool_call['function'].get('arguments', '{}')
                    try:
                        args_dict = _json.loads(args) if isinstance(args, str) else args
                    except Exception as e:
                        logger.error(f"Failed to parse tool arguments for {fn}: {e}")
                        tool_result = {"error": f"Failed to parse tool arguments: {e}"}
                    else:
                        tool_fn = TOOL_FUNCTIONS.get(fn)
                        if tool_fn:
                            try:
                                tool_result = tool_fn(**args_dict)
                                logger.info(f"Executed tool {fn}: {tool_result}")
                            except Exception as e:
                                logger.error(f"Error executing tool {fn}: {e}")
                                tool_result = {"error": f"Tool '{fn}' execution failed: {e}"}
                        else:
                            logger.warning(f"No tool function registered for {fn}")
                            tool_result = {"error": f"Tool '{fn}' is not available."}
                    # 4. Create tool message per OpenAI spec
                    tool_msg = {
                        "role": "tool",
                        "content": _json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result,
                        "tool_call_id": tool_call.get("id")
                    }
                    # 5. Sync tool message to ledger
                    tool_sync = [{
                        "user_id": message.user_id,
                        "platform": platform,
                        "platform_msg_id": None,
                        "role": "tool",
                        "content": tool_msg["content"],
                        "model": message.model if hasattr(message, 'model') else None,
                        "tool_calls": None,
                        "function_call": None,
                        "tool_call_id": tool_msg["tool_call_id"]
                    }]
                    ledger_buffer = await sync_with_ledger(
                        user_id=message.user_id,
                        platform=platform,
                        snapshot=tool_sync,
                        error_prefix="Error forwarding tool message to ledger",
                        logger=logger
                    )
                    # 6. Update message buffer for next request
                    message_buffer = [
                        {
                            "role": msg["role"],
                            "content": msg["content"],
                            **({"tool_calls": msg["tool_calls"]} if msg.get("tool_calls") is not None else {}),
                            **({"function_call": msg["function_call"]} if msg.get("function_call") is not None else {}),
                            **({"tool_call_id": msg["tool_call_id"]} if msg.get("tool_call_id") is not None else {}),
                        }
                        for msg in ledger_buffer
                    ]
                    updated_request = updated_request.copy(update={"messages": message_buffer})
            tool_loop_count += 1
            continue  # Loop again with updated buffer
        # 7. If we get a real assistant message (content), break and return
        if proxy_response.response:
            final_response = proxy_response
            break
        tool_loop_count += 1
    if final_response is None:
        final_response = proxy_response

    # Ensure the assistant's final response is appended to updated_request.messages
    if final_response and final_response.response:
        assistant_msg = {
            "role": "assistant",
            "content": final_response.response,
        }
        # Optionally include tool_calls and function_call if present
        if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
            assistant_msg["tool_calls"] = final_response.tool_calls
        if hasattr(final_response, 'function_call') and final_response.function_call:
            assistant_msg["function_call"] = final_response.function_call
        updated_request.messages.append(assistant_msg)

    # Run post-execution brainlets
    post_brainlets = [b for b in brainlets_sorted if b.get('execution_stage') == 'post']
    post_brainlets_output = {}
    for brainlet in post_brainlets:
        modes = brainlet.get('modes', [])
        if message.model in modes:
            logger.debug(f"Running post brainlet: {brainlet['name']} for mode: {message.model}")
            brainlet_name = brainlet['name']
            brainlet_func = getattr(app.brainlets, brainlet_name, None)
            if brainlet_func:
                logger.debug(f"Found post brainlet function: {brainlet_func.__name__}")
                # Pass the latest brainlets_output and updated_request (with final_response)
                post_result = await brainlet_func(brainlets_output, updated_request)
                if post_result and isinstance(post_result, dict):
                    logger.debug(f"Post brainlet {brainlet_name} returned: {post_result}")
                    # Sync any lists of message dicts inside the dict
                    for val in post_result.values():
                        if isinstance(val, list):
                            for msg_dict in val:
                                logger.debug(f"Processing post brainlet message from dict value: {msg_dict}")
                                if isinstance(msg_dict, dict) and msg_dict.get("role") in ("assistant", "tool"):
                                    sync_snapshot = [
                                        {
                                            "user_id": message.user_id,
                                            "platform": platform,
                                            "platform_msg_id": None,
                                            "role": msg_dict.get("role"),
                                            "content": msg_dict.get("content"),
                                            "model": message.model if hasattr(message, 'model') else None,
                                            "tool_calls": msg_dict.get("tool_calls"),
                                            "function_call": msg_dict.get("function_call"),
                                            "tool_call_id": msg_dict.get("tool_call_id"),
                                        }
                                    ]
                                    try:
                                        logger.debug(f"Syncing post brainlet message to ledger: {sync_snapshot}")
                                        await sync_with_ledger(
                                            user_id=message.user_id,
                                            platform=platform,
                                            snapshot=sync_snapshot,
                                            error_prefix=f"Error forwarding post brainlet ({brainlet_name}) message to ledger",
                                            logger=logger
                                        )
                                        logger.debug("Ledger sync successful.")
                                    except Exception as e:
                                        logger.error(f"Ledger sync failed for post brainlet {brainlet_name}: {e}")
                elif post_result and isinstance(post_result, list):
                    for msg_dict in post_result:
                        if isinstance(msg_dict, dict) and msg_dict.get("role") in ("assistant", "tool"):
                            sync_snapshot = [
                                {
                                    "user_id": message.user_id,
                                    "platform": platform,
                                    "platform_msg_id": None,
                                    "role": msg_dict.get("role"),
                                    "content": msg_dict.get("content"),
                                    "model": message.model if hasattr(message, 'model') else None,
                                    "tool_calls": msg_dict.get("tool_calls"),
                                    "function_call": msg_dict.get("function_call"),
                                    "tool_call_id": msg_dict.get("tool_call_id"),
                                }
                            ]
                            try:
                                logger.debug(f"Syncing post brainlet message to ledger: {sync_snapshot}")
                                await sync_with_ledger(
                                    user_id=message.user_id,
                                    platform=platform,
                                    snapshot=sync_snapshot,
                                    error_prefix=f"Error forwarding post brainlet ({brainlet_name}) message to ledger",
                                    logger=logger
                                )
                                logger.debug("Ledger sync successful.")
                            except Exception as e:
                                logger.error(f"Ledger sync failed for post brainlet {brainlet_name}: {e}")
                post_brainlets_output[brainlet_name] = post_result
    # Optionally merge post_brainlets_output into final_response if needed

    logger.debug(f"brain: /api/multiturn Returns:\n{final_response.model_dump_json(indent=4)}")
    return final_response
