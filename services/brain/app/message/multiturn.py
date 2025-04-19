"""
This module defines an API endpoint for handling multi-turn conversation requests 
and forwarding them to an internal proxy service. It acts as a simple proxy 
without additional processing.

Modules:
    app.config: Provides configuration settings for the application.
    shared.models.proxy: Contains data models for ProxyMultiTurnRequest and ProxyResponse.
    shared.log_config: Provides a logger for logging messages.
    httpx: Used for making asynchronous HTTP requests.
    fastapi: Provides tools for building API routes and handling HTTP exceptions.

Classes:
    None

Functions:
    outgoing_multiturn_message(message: ProxyMultiTurnRequest) -> ProxyResponse:
        Handles incoming multi-turn conversation requests, forwards them to the 
        internal proxy service, and returns the response.

Dependencies:
    - app.config.PROXY_URL: The base URL for the proxy service.
    - ProxyMultiTurnRequest: The request model for multi-turn conversations.
    - ProxyResponse: The response model for multi-turn conversations.
    - httpx.AsyncClient: Used for making asynchronous HTTP requests.
    - fastapi.APIRouter: Used for defining API routes.
    - fastapi.HTTPException: Used for raising HTTP exceptions.
"""

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse, ProxyMessage
from shared.models.intents import IntentRequest

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


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

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            intents_address, intents_port = shared.consul.get_service_address('intents')
            if not intents_address or not intents_port:
                logger.error("Intents service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Intents service is unavailable."
                )
            
            response = await client.post(f"http://{intents_address}:{intents_port}/intents", json=intentreq.model_dump())
            response.raise_for_status()

            payload['messages'] = response.json()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from intents service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to intents service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to intents service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to intents service: {req_err}"
            )

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
            if not proxy_address or not proxy_port:
                logger.error("Proxy service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Proxy service is unavailable."
                )
            
            response = await client.post(f"http://{proxy_address}:{proxy_port}/from/api/multiturn", json=payload)
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from proxy service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to proxy service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to proxy service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to proxy service: {req_err}"
            )

    try:
        json_response = response.json()

        proxy_response = ProxyResponse.model_validate(json_response)

    except Exception as e:
        logger.error(f"Error parsing response from proxy service: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse response from proxy service."
        )

    # check for intents on the model's output. Note that we don't have a shared model+user function
    # because some intents are only relevant to the user's or model's output.]
    intentreq = IntentRequest(
        mode=True,
        component="proxy",
        memory=True,
        message=[ProxyMessage(role="assistant", content=proxy_response.response)]
    )

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            intents_address, intents_port = shared.consul.get_service_address('intents')
            if not intents_address or not intents_port:
                logger.error("Intents service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Intents service is unavailable."
                )
            print(intentreq.model_dump())  
            response = await client.post(f"http://{intents_address}:{intents_port}/intents", json=intentreq.model_dump())
            response.raise_for_status()

            # Update proxy_response.response to the content of the returned ProxyMessage
            returned_messages = response.json()
            if isinstance(returned_messages, list) and returned_messages:
                proxy_response.response = returned_messages[0].get('content', proxy_response.response)

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from intents service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to intents service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to intents service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to intents service: {req_err}"
            )

    logger.debug(f"/message/multiturn/incoming Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response
