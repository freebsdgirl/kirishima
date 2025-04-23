import httpx

from pydantic import BaseModel
from shared.models.ledger import CanonicalUserMessage
from shared.models.proxy import ProxyOneShotRequest

from typing import List

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


class SummaryRequest(BaseModel):
    """
    Request model for summarizing user messages.
    """
    messages: List[CanonicalUserMessage]
    max_tokens: int


@router.post("/summary/user", status_code=status.HTTP_201_CREATED)
async def summary_user(request: SummaryRequest):
    """
    Summarize the user's messages.
    """
    logger.debug(f"Received summary request: {request}")

    # Convert messages to a single string in the format:
    # "Randi: thing the user said\nKirishima: thing the assistant said\n..."
    user_label = "Randi"
    assistant_label = "Kirishima"
    lines = []
    for msg in request.messages:
        if msg.role == "user":
            lines.append(f"{user_label}: {msg.content}")
        elif msg.role == "assistant":
            lines.append(f"{assistant_label}: {msg.content}")
    conversation_str = "\n".join(lines)

    logger.debug(f"Conversation string for summary: {conversation_str}")
    print(conversation_str)

    prompt = f"""[INST]<<SYS>>### Task: Summarize the following conversation between two people in a clear and concise manner.



### Conversation

{conversation_str}



### Instructions

- The summary should capture the main points and tone of the conversation.
- The summary should be no more than 128 tokens in length.
- The summary should be a single paragraph.

<</SYS>>[/INST]"""

    payload = ProxyOneShotRequest(
            model="nemo:latest",
            prompt=prompt,
            temperature=0.3,
            max_tokens=request.max_tokens
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

            response = await client.post(f"http://{proxy_address}:{proxy_port}/from/api/completions", json=payload.model_dump())
            response.raise_for_status()
            proxy_response = response.json()
            summary_text = proxy_response.get("response")
            return {"summary": summary_text}

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from proxy service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from proxy service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to proxy service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )