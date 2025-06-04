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
    updated_request = message.copy(update={
        "memories": [m.model_dump() for m in memories],
        "messages": message.messages,  # Use messages directly, no sanitization
        "username": username,
        "summaries": summaries,
        "platform": platform
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
                "content": m.get("content")
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
        # Use dicts for messages, not ChatMessage
        updated_request = updated_request.copy(update={
            "messages": [{"role": msg["role"], "content": msg["content"]} for msg in ledger_buffer]
        })
    except Exception as e:
        logger.error(f"Error sending messages to ledger sync endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync messages with ledger service."
        )

    # send the payload to the proxy service
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


    try:
        # Send proxy_response to ledger as a single RawUserMessage
        user_id = await get_admin_user_id()
        platform = 'api'
        platform_msg_id = None
        sync_snapshot = [{
            "user_id": user_id,
            "platform": platform,
            "platform_msg_id": platform_msg_id,
            "role": "assistant",
            "content": proxy_response.response
        }]
        await post_to_service(
            'ledger',
            f'/ledger/user/{user_id}/sync',
            {"snapshot": sync_snapshot},
            error_prefix="Error forwarding to ledger service (proxy_response)"
        )

    except Exception as e:
        logger.error(f"Error sending proxy_response to ledger sync endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync proxy_response with ledger service: {e}"
        )

    # last, update our last seen timestamp
    update_last_seen(LastSeen(
        user_id=user_id,
        platform=platform
    ))

    # update divoom with emoji response
    try:
        await update_divoom(user_id)
    except Exception as e:
        logger.error(f"Error updating divoom with emoji response: {e}")

    logger.debug(f"brain: /api/multiturn Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response
