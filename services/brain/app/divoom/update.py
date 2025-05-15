"""
This module defines an API endpoint for updating the Divoom device with an emoji response
based on a user's message history. It retrieves user messages from the ledger service,
sanitizes and transforms them, sends them to a language model via a proxy service to
generate an emoji, and then forwards the emoji to the Divoom device.
Endpoints:
    POST /divoom
        - Accepts a user_id as a query parameter.
        - Retrieves the user's message history from the ledger service.
        - Swaps the roles in the messages for processing.
        - Sanitizes the messages and constructs a DivoomRequest.
        - Sends the request to the proxy service to generate an emoji response.
        - Forwards the emoji to the Divoom device.
        - Returns the proxy response containing the emoji.
Raises:
    HTTPException: If messages cannot be retrieved, parsed, or sent to the Divoom device,
    or if no emoji is found in the response.
"""
import shared.consul
from shared.config import TIMEOUT, LLM_DEFAULTS

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx

from fastapi import APIRouter, HTTPException, status

from shared.models.proxy import ProxyResponse, DivoomRequest

from app.util import sanitize_messages, post_to_service

router = APIRouter()
@router.post("/divoom", response_model=ProxyResponse)
async def update_divoom(user_id: str):
    logger.debug(f"/divoom Request: {user_id}")
    
    messages = []

    try:
        ledger_address, ledger_port = shared.consul.get_service_address('ledger')

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"http://{ledger_address}:{ledger_port}/user/{user_id}/messages")
            response.raise_for_status()
            fullmessages = response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No messages found for {user_id}, skipping.")
        else:
            logger.error(f"HTTP error from ledger: {e.response.status_code} - {e.response.text}")
            raise

    except Exception as e:
        logger.error(f"Failed to contact ledger to get a list of messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve messages: {e}")

    if fullmessages is None or len(fullmessages) == 0:
        logger.warning("No messages found for the specified user.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No messages found for the specified user."
        )

    for m in fullmessages:
        if m.get("role") == "user":
            m["role"] = "assistant"
        else:
            m["role"] = "user"
        m["content"] = m.get("content", "")
        messages.append(m)

    # sanitize messages
    messages = sanitize_messages(messages)
    
    # Start constructing our ProxyiMessageRequest
    proxy_request = DivoomRequest(
        messages=messages,
        model = LLM_DEFAULTS['model'],
        temperature=LLM_DEFAULTS['temperature'],
        max_tokens=LLM_DEFAULTS['max_tokens'],
    )

    # send to LLM via imessage endpoint in proxy service
    response = await post_to_service(
        'proxy', '/divoom', proxy_request.model_dump(),
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

    # validate the response
    response_content = proxy_response.response
    if not isinstance(response_content, str):
        logger.debug(f"proxy_response.response is not a string: {type(response_content)}. Converting to string.")
        response_content = str(response_content)

    emoji = response_content.strip()
    if emoji is None or len(emoji) == 0:
        logger.warning("No emoji found in the response.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No emoji found in the response."
        )
    # send the emoji to the divoom
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"http://host.docker.internal:5551/send", json={"emoji": emoji})
            response.raise_for_status()

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from divoom: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error sending to divoom: {e.response.text}"
        )

    except Exception as e:
        logger.error(f"Failed to contact divoom: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send to divoom: {e}")


    logger.debug(f"/divoom Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response