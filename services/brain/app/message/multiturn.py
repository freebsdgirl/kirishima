"""
This module implements the multi-turn conversation endpoint for the brain service.
It provides the `/api/multiturn` FastAPI route, which orchestrates a complex workflow for handling multi-turn chat requests, including:
- Retrieving user memories and context
- Running pre- and post-execution brainlets (customizable logic modules)
- Managing agent-managed prompts and recent summaries
- Interfacing with a proxy service for LLM responses
- Executing tool/function calls in a loop as required by the LLM
- Synchronizing all relevant messages with a ledger service for audit/history
- Handling error cases and logging throughout the process
Key Functions:
- `get_agent_managed_prompt(user_id: str) -> str`: Fetches all enabled prompts for a user from the brainlets database, returning them as a formatted string.
- `outgoing_multiturn_message(message: MultiTurnRequest) -> ProxyResponse`: Main endpoint handler for multi-turn chat, coordinating memory retrieval, brainlet execution, proxy interaction, tool call execution, and ledger synchronization.
Dependencies:
- FastAPI, httpx, sqlite3, shared models and utilities, app-specific modules for memory, tools, and brainlets.
Configuration:
- Reads from `/app/config/config.json` and `/app/app/tools.json` for settings and tool definitions.
Logging:
- Uses a structured logger for debugging and error reporting throughout the workflow.
"""
 
from shared.models.proxy import MultiTurnRequest, ProxyResponse
from shared.models.ledger import ToolSyncRequest
from app.util import sync_with_ledger, get_admin_user_id, post_to_service, get_user_alias, sanitize_messages, get_recent_summaries

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import json
import sqlite3
from pathlib import Path
import inspect
import httpx
import os

import app.brainlets
from collections import defaultdict, deque
from app.tools.stickynotes import check_stickynotes

from app.tools import TOOL_FUNCTIONS

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


def get_agent_managed_prompt(user_id: str) -> str:
    """
    Fetch all enabled prompts for the user from the brainlets database, ordered by timestamp.
    Returns a string with each prompt on a new line, prefixed by '- '.
    If no prompts are found, returns an empty string.
    """
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        db_path = _config['db']['brainlets']
        if not db_path or not Path(db_path).exists():
            return ""
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT prompt FROM prompt WHERE user_id = ? AND enabled = 1 ORDER BY timestamp", (user_id,))
            rows = cursor.fetchall()
            if not rows:
                return ""
            return "\n".join(f"- {row[0]}" for row in rows)
    except Exception as e:
        logger.error(f"Error fetching agent-managed prompts: {e}")
        return ""


@router.post("/api/multiturn", response_model=ProxyResponse)
async def outgoing_multiturn_message(message: MultiTurnRequest) -> ProxyResponse:
    """
    Handles multi-turn conversation requests by processing messages through a complex workflow:
    - Retrieves memories and user context
    - Runs pre-execution brainlets
    - Sends request to proxy service
    - Handles tool calls and function execution
    - Syncs messages with ledger service
    - Runs post-execution brainlets

    Args:
        message (MultiTurnRequest): The incoming multi-turn conversation request

    Returns:
        ProxyResponse: The final response from the conversation processing pipeline
    """
    logger.debug(f"brain: /api/multiturn Request:")

    # Memories only apply to ollama requests - we should not be sending them to openai requests.
    memories = []
    if message.provider == "ollama":
        # sanitize proxy messages
        message.messages = sanitize_messages(message.messages)

    # get username
    if not message.user_id:
        message.user_id = await get_admin_user_id()
    username = await get_user_alias(message.user_id)
    platform = message.platform or "api"

    # construct the agent-managed prompt
    agent_prompt = get_agent_managed_prompt(message.user_id)
    
    # get a list of the last 4 summaries - this returns a formatted string
    summaries = await get_recent_summaries(limit=1)
    if not summaries:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )
    # summaries is already a formatted string, no need to re-parse or join

    # Build new MultiTurnRequest with updated fields
    with open('/app/app/tools.json') as f:
        all_tools = json.load(f)
    
    # Resolve provider from mode to determine which tools to include
    def resolve_provider_from_mode(mode: str):
        """Resolve provider from mode using config.json"""
        llm_modes = _config.get("llm", {}).get("mode", {})
        mode_config = llm_modes.get(mode) or llm_modes.get("default")
        if mode_config:
            return mode_config.get("provider", "openai")
        return "openai"  # fallback
    
    provider = resolve_provider_from_mode(message.model)
    
    # Use all tools for all providers
    tools = all_tools

    updated_request = message.copy(update={
        "memories": [m.model_dump() for m in memories],
        "messages": message.messages,
        "username": username,
        "summaries": summaries,
        "platform": platform,
        "tools": tools,
        "agent_prompt": agent_prompt,
        "provider": provider  # Set the resolved provider
    })

    # --- Send last 4 messages to ledger ---
    try:
        last_msgs = updated_request.messages[-4:]
        sync_snapshot = [
            {
                "platform": platform,
                "platform_msg_id": None,
                "role": m.get("role"),
                "content": m.get("content"),
                "model": message.model if hasattr(message, 'model') else None,
                # Only include the first tool_call dict if tool_calls is a non-empty list, else dict, else None
                "tool_calls": m.get("tool_calls")[0] if isinstance(m.get("tool_calls"), list) and m.get("tool_calls") else m.get("tool_calls") if isinstance(m.get("tool_calls"), dict) else None,
                "function_call": m.get("function_call"),
            }
            for m in last_msgs
        ]

        ledger_port = os.getenv("LEDGER_PORT", 4203)

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            get_sync = await client.post(f"http://ledger:{ledger_port}/sync/user", json={"snapshot": sync_snapshot})
            get_sync.raise_for_status()
        
            # Get updated buffer
            get_response = await client.get(f"http://ledger:{ledger_port}/sync/get")
            get_response.raise_for_status()
            ledger_buffer = get_response.json()
        
        # Use dicts for messages, not ChatMessage, and preserve tool_calls/function_call/tool_call_id fields
        updated_request = updated_request.model_copy(update={
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

    # Topological sort to respect depends_on
    def topo_sort_brainlets(brainlets):
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
                brainlets_output[brainlet_name] = brainlet_result

    # Merge brainlets_output lists into updated_request.messages
    # brainlets output is *not* saved to ledger's tool endpoint
    for v in brainlets_output.values():
        if isinstance(v, list):
            updated_request.messages.extend(v)
        elif isinstance(v, dict):
            # If the dict contains a list under any key, extend messages with it
            for val in v.values():
                if isinstance(val, list):
                    updated_request.messages.extend(val)

    # technically this should be a brainlet, but it lives here for now.
    # check for any stickynotes that are due and return them as tool calls
    # these also are *not* saved to the ledger's tool endpoint
    tools_calls = await check_stickynotes(message.user_id)
    if tools_calls:
        # if the list isn't empty, append the dicts to the messages.
        # they are already formatted as OpenAI tool calls.
        updated_request.messages.extend(tools_calls)

    # send the payload to the proxy service and handle tool call loop
    final_response = None
    message_buffer = updated_request.messages
    tool_loop_count = 0
    MAX_TOOL_LOOPS = 10
    while tool_loop_count < MAX_TOOL_LOOPS:
        # 1. Send to proxy
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                proxy_port = os.getenv("PROXY_PORT", 4205)
                response = await client.post(f"http://proxy:{proxy_port}/api/multiturn", json=updated_request.model_dump())
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Error sending request to proxy service: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to send request to proxy service: {e}"
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
                        args_dict = json.loads(args) if isinstance(args, str) else args
                    except Exception as e:
                        logger.error(f"Failed to parse tool arguments for {fn}: {e}")
                        tool_result = {"error": f"Failed to parse tool arguments: {e}"}
                    else:
                        tool_fn = TOOL_FUNCTIONS.get(fn)
                        if tool_fn:
                            try:
                                if inspect.iscoroutinefunction(tool_fn):
                                    tool_result = await tool_fn(**args_dict)
                                else:
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
                        "content": json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result,
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
            
            # Continue looping if we had tool calls that need follow-up
            if tool_calls:
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
                post_brainlets_output[brainlet_name] = post_result
    # Optionally merge post_brainlets_output into final_response if needed

    logger.debug(f"brain: /api/multiturn Returns:\n{final_response.model_dump_json(indent=4)}")
    return final_response
