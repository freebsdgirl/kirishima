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
from app.util import get_admin_user_id, post_to_service, get_user_alias
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
    Forwards a multi-turn conversation request to the internal multi-turn 
    endpoint (/api/multiturn). This endpoint acts as a simple proxy with no
    additional processing.

    Args:
        message (ProxyMultiTurnRequest): The multi-turn conversation request.

    Returns:
        ProxyResponse: The response from the internal proxy service.

    Raises:
        HTTPException: If any error occurs when contacting the proxy service.
    """
    logger.debug(f"brain: /api/multiturn Request:\n{message.model_dump_json(indent=4)}")

    # get a list of memories
    memory_query = MemoryListQuery(component="proxy", limit=100, mode=message.model)
    memories = await list_memory(memory_query)

    # No longer sanitize proxy messages
    # sanitized_messages = sanitize_messages(message.messages)

    # get username
    user_id = await get_admin_user_id()
    username = await get_user_alias(user_id)
    platform = message.platform or "api"

    # get a list of the last 4 summaries - this returns a List[Summary]
    summaries = ""
    try:
        chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"http://{chromadb_address}:{chromadb_port}/summary?user_id={user_id}&limit=4")
            response.raise_for_status()
            summaries_list = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No summaries found for {user_id}, skipping.")
            summaries_list = []
        else:
            logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
            raise
    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")
    if not summaries_list:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )
    summary_lines = []
    for s in summaries_list:
        summary = Summary.model_validate(s) if not isinstance(s, Summary) else s
        meta = summary.metadata
        if meta is not None:
            if meta.summary_type.value == "daily":
                date_str = meta.timestamp_begin.split(" ")[0]
                label = date_str
            else:
                label = meta.summary_type.value
        else:
            label = "summary"
        summary_lines.append(f"[{label}] {summary.content}")
    summaries = "\n".join(summary_lines)

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
    try:
        platform_msg_id = None
        last_msgs = updated_request.messages[-4:]
        sync_snapshot = [
            {
                "user_id": user_id,
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
        ledger_response = await post_to_service(
            'ledger',
            f'/ledger/user/{user_id}/sync',
            {"snapshot": sync_snapshot},
            error_prefix="Error forwarding to ledger service"
        )
        ledger_buffer = ledger_response.json()
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

    # send the payload to the proxy service and handle tool call loop
    from app.tools import TOOL_FUNCTIONS
    import json as _json
    final_response = None
    message_buffer = updated_request.messages
    tool_loop_count = 0
    MAX_TOOL_LOOPS = 5
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
            "user_id": user_id,
            "platform": platform,
            "platform_msg_id": None,
            "role": "assistant",
            "content": proxy_response.response,
            "model": message.model if hasattr(message, 'model') else None,
            # Only include the first tool_call dict if tool_calls is a non-empty list
            "tool_calls": proxy_response.tool_calls[0] if isinstance(proxy_response.tool_calls, list) and proxy_response.tool_calls else None,
            "function_call": getattr(proxy_response, 'function_call', None),
        }]
        await post_to_service(
            'ledger',
            f'/ledger/user/{user_id}/sync',
            {"snapshot": sync_snapshot},
            error_prefix="Error forwarding to ledger service (proxy_response)"
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
                        "user_id": user_id,
                        "platform": platform,
                        "platform_msg_id": None,
                        "role": "tool",
                        "content": tool_msg["content"],
                        "model": message.model if hasattr(message, 'model') else None,
                        "tool_calls": None,
                        "function_call": None,
                        "tool_call_id": tool_msg["tool_call_id"]
                    }]
                    ledger_response = await post_to_service(
                        'ledger',
                        f'/ledger/user/{user_id}/sync',
                        {"snapshot": tool_sync},
                        error_prefix="Error forwarding tool message to ledger"
                    )
                    ledger_buffer = ledger_response.json()
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
    logger.debug(f"brain: /api/multiturn Returns:\n{final_response.model_dump_json(indent=4)}")
    return final_response
