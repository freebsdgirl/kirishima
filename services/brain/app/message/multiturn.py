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
    @router.post("/message/multiturn/incoming", response_model=ProxyResponse):
        endpoint (/from/api/multiturn). Acts as a proxy with no additional 
        processing. Handles intents detection, retrieves the current mode, 
        queries memory, sanitizes messages, and processes the proxy response.
"""
import json

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse, ProxyMessage
from shared.models.intents import IntentRequest
from shared.models.chromadb import MemoryListQuery

from app.memory.list import list_memory
from app.modes import mode_get

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import re

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


def sanitize_messages(messages):
    """
    Sanitizes a list of messages by removing HTML details tags and stripping whitespace.
    
    Args:
        messages (list): A list of message dictionaries to sanitize.
    
    Returns:
        list: The sanitized list of messages with details tags removed and whitespace stripped.
    
    Logs an error for any non-dictionary messages encountered during processing.
    """
    for message in messages:
        if isinstance(message, dict):
            content = message.get('content', '')
            content = re.sub(r'<details>.*?</details>', '', content, flags=re.DOTALL)
            content = content.strip()
            message['content'] = content
        else:
            logger.error(f"Expected message to be a dict, but got {type(message)}")
    return messages


async def post_to_service(service_name, endpoint, payload, error_prefix, timeout=60):
    """
    Sends a POST request to a specified service endpoint using Consul service discovery.
    
    Args:
        service_name (str): Name of the target service.
        endpoint (str): API endpoint path to call.
        payload (dict): JSON payload to send with the request.
        error_prefix (str): Prefix for error logging and exception messages.
        timeout (int, optional): Request timeout in seconds. Defaults to 60.
    
    Returns:
        httpx.Response: The response from the service.
    
    Raises:
        HTTPException: If service is unavailable, connection fails, or HTTP error occurs.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        address, port = shared.consul.get_service_address(service_name)
        if not address or not port:
            logger.error(f"{service_name.capitalize()} service address or port is not available.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{service_name.capitalize()} service is unavailable."
            )
        url = f"http://{address}:{port}{endpoint}"
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from {service_name} service: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"{error_prefix}: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to {service_name} service: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to {service_name} service: {req_err}"
            )


@router.post("/message/multiturn/incoming", response_model=ProxyResponse)
async def outgoing_multiturn_message(message: ProxyMultiTurnRequest) -> ProxyResponse:
    """
    Forwards a multi-turn conversation request to the internal multi-turn 
    endpoint (/from/api/multiturn). This endpoint acts as a simple proxy with no
    additional processing.

    Args:
        message (ProxyMultiTurnRequest): The multi-turn conversation request.

    Returns:
        ProxyResponse: The response from the internal proxy service.

    Raises:
        HTTPException: If any error occurs when contacting the proxy service.
    """
    logger.debug(f"/message/multiturn/incoming Request:\n{message.model_dump_json(indent=4)}")

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

    memory_query = MemoryListQuery(component="proxy", limit=100, mode=mode)
    memories = await list_memory(memory_query)
    payload["memories"] = [m.model_dump() for m in memories]

    # Sanitize proxy messages
    payload["messages"] = sanitize_messages(payload['messages'])

    response = await post_to_service(
        'proxy', '/from/api/multiturn', payload,
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
        message=[ProxyMessage(role="assistant", content=response_content)]
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

    logger.debug(f"/message/multiturn/incoming Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response
