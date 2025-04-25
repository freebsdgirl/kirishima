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
import json

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse, ChatMessage
from shared.models.intents import IntentRequest
from shared.models.chromadb import MemoryListQuery

from app.memory.list import list_memory
from app.modes import mode_get
from app.util import get_admin_user_id, sanitize_messages, post_to_service

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

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

    response = await post_to_service(
        'intents', '/intents', intentreq.model_dump(),
        error_prefix="Error forwarding to intents service"
    )
    try:
        payload['messages'] = response.json()
    except Exception as e:
        logger.debug(f"Error decoding JSON from intents service response: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid JSON response from intents service."
        )

    # get the current mode
    mode_response = mode_get()
    if hasattr(mode_response, 'body'):
        mode_json = json.loads(mode_response.body)
        mode = mode_json.get('message')
    else:
        mode = None

    # get a list of memories
    memory_query = MemoryListQuery(component="proxy", limit=100, mode=mode)
    memories = await list_memory(memory_query)
    payload["memories"] = [m.model_dump() for m in memories]

    # Sanitize proxy messages
    payload["messages"] = sanitize_messages(payload['messages'])

    # --- Send last 4 messages to ledger as RawUserMessage ---
    try:
        user_id = await get_admin_user_id()
        platform = 'api'
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

    # get a list of summaries - this returns a List[UserSummary]
    async with httpx.AsyncClient(timeout=30) as client:
        address, port = shared.consul.get_service_address('ledger')
        if not address or not port:
            logger.error(f"ledger service address or port is not available.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"ledger service is unavailable."
            )
        try:
            summary_response = await client.get(f"http://{address}:{port}/summaries/user/{user_id}?limit=4")
            summary_response.raise_for_status()
            summaries = summary_response.json().get("summaries", [])
            combined_content = "\n".join(s["content"] for s in summaries)
        
            payload["summaries"] = combined_content

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from ledger service: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"ledger: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to ledger service: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to ledger service: {req_err}"
            )
    
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
            detail="Failed to parse response from proxy service."
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
    response = await post_to_service(
        'intents', '/intents', intentreq.model_dump(),
        error_prefix="Error forwarding to intents service"
    )
    try:
        returned_messages = response.json()
    except Exception as e:
        logger.debug(f"Error decoding JSON from intents service response (final): {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid JSON response from intents service (final)."
        )
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
            detail="Failed to sync proxy_response with ledger service."
        )

    logger.debug(f"brain: /api/multiturn Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response
