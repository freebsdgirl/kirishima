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
from shared.config import TIMEOUT
import shared.consul

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse, ChatMessage
from shared.models.intents import IntentRequest
from shared.models.memory import MemoryListQuery
from shared.models.summary import Summary
from shared.models.notification import LastSeen

from app.memory.get import list_memory
from app.modes import mode_get
from app.util import get_admin_user_id, sanitize_messages, post_to_service, get_user_alias
from app.last_seen import update_last_seen
from app.intents.intents import process_intents
from app.divoom.update import update_divoom

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import json
import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/api/multiturn", response_model=ProxyResponse)
async def outgoing_multiturn_message(message: ProxyMultiTurnRequest) -> ProxyResponse:
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

    payload = message.model_dump()

    # check for intents on user input. the only intent we're checking for right now is mode.
    intentreq = IntentRequest(
        mode=True,
        memory=True,
        component="proxy",
        message=message.messages
    )

    response = await process_intents(intentreq)

    payload['messages'] = [ m.model_dump() for m in response ]

    # get the current mode
    mode_response = mode_get()
    mode_json = json.loads(mode_response.body)

    payload["mode"] = mode_json.get('message')

    # get a list of memories
    memory_query = MemoryListQuery(component="proxy", limit=100, mode=payload['mode'])
    memories = await list_memory(memory_query)
    payload["memories"] = [m.model_dump() for m in memories]

    # Sanitize proxy messages
    payload["messages"] = sanitize_messages(payload['messages'])

    # --- Send last 4 messages to ledger as RawUserMessage ---
    try:
        user_id = await get_admin_user_id()
        payload["username"] = await get_user_alias(user_id)
        platform = payload.get("platform", "api")
        platform_msg_id = None
        last_msgs = payload["messages"][-4:]
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
        # sync with ledger
        ledger_response = await post_to_service(
            'ledger',
            f'/ledger/user/{user_id}/sync',
            {"snapshot": sync_snapshot},
            error_prefix="Error forwarding to ledger service"
        )
        # Convert ledger buffer to ProxyMessage list and replace payload['messages']
        ledger_buffer = ledger_response.json()
        payload["messages"] = [ChatMessage(role=msg["role"], content=msg["content"]).model_dump() for msg in ledger_buffer]

    except Exception as e:
        logger.error(f"Error sending messages to ledger sync endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync messages with ledger service."
        )

    # get a list of the last 4 summaries - this returns a List[Summary]
    payload["summaries"] = ""

    try:
        chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"http://{chromadb_address}:{chromadb_port}/summary?user_id={user_id}&limit=4")
            response.raise_for_status()
            summaries = response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No summaries found for {user_id}, skipping.")
        else:
            logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
            raise

    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")

    if not summaries:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )

    # construct summary string here
    summary_lines = []
    for s in summaries:
        summary = Summary.model_validate(s) if not isinstance(s, Summary) else s
        meta = summary.metadata
        if meta is not None:
            if meta.summary_type.value == "daily":
                # Split on space to get the date part
                date_str = meta.timestamp_begin.split(" ")[0]
                label = date_str
            else:
                label = meta.summary_type.value
        else:
            label = "summary"
        summary_lines.append(f"[{label}] {summary.content}")

    payload["summaries"] = "\n".join(summary_lines)

    # send the payload to the proxy service
    response = await post_to_service(
        'proxy', '/api/multiturn', payload,
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

    """
    Process and validate the proxy response by converting it to a string,
    forwarding it to the intents service, and potentially updating the response
    based on the intents service's returned messages.
    
    Ensures the proxy response is a string, sends it to the intents service,
    and updates the proxy response with the first returned message's content
    if available.
    """
    response_content = proxy_response.response

    if not isinstance(response_content, str):
        logger.debug(f"proxy_response.response is not a string: {type(response_content)}. Converting to string.")
        response_content = str(response_content)

    intentreq = IntentRequest(
        mode=True,
        component="proxy",
        memory=True,
        message=[ChatMessage(role="assistant", content=response_content)]
    )

    response = await process_intents(intentreq)

    returned_messages = [ m.model_dump() for m in response ]

    if isinstance(returned_messages, list) and returned_messages:
        proxy_response.response = returned_messages[0].get('content', proxy_response.response)

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
