from shared.config import TIMEOUT, LLM_DEFAULTS
from shared.models.proxy import ProxyDiscordDMRequest, ProxyResponse, ProxyRequest, IncomingMessage, ChatMessages

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from app.util import build_multiturn_prompt
from app.prompts.dispatcher import get_system_prompt

import app.config

import httpx
import json
from datetime import datetime
import re

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/discord/dm")
async def discord_dm(request: ProxyDiscordDMRequest) -> ProxyResponse:
    """
    Send a direct message to a Discord user.
    
    Args:
        request (ProxyDiscordDMRequest): The request object containing the message details.
    
    Returns:
        dict: A dictionary containing the status of the message sending operation.
    
    Raises:
        HTTPException: If there is an error in sending the message.
    """
    logger.debug(f"/discord/dm Request: {request}")

    # assemble a minimal ProxyRequest just to generate the system prompt
    # it only needs .message, .user_id, .context, .mode, .memories
    proxy_req = ProxyRequest(
        message=IncomingMessage(
            platform="discord", 
            sender_id=request.contact.id,
            text=request.message.content,
            timestamp=request.message.timestamp,
            metadata={
                "name": request.message.display_name
            }
        ),
        user_id=request.contact.id,
        context=request.message.display_name,
        mode=request.mode,
        memories=request.memories,
        summaries=request.summaries
    )

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(proxy_req)

    # 4) build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(ChatMessages(messages=request.messages), system_prompt)

    # Construct the payload for the Ollama API call
    payload = {
        "model": LLM_DEFAULTS["model"],
        "prompt": full_prompt,
        "temperature": LLM_DEFAULTS["temperature"],
        "max_tokens": LLM_DEFAULTS["max_tokens"],
        "stream": False,
        "raw": True
    }

    logger.debug(f"🦙 Request to Ollama API:\n{json.dumps(payload, indent=4, ensure_ascii=False)}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(f"{app.config.OLLAMA_URL}/api/generate", json=payload)
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from Ollama API: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from language model service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to Ollama API: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error in Ollama API: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in language model service: {e}"
            )

    try:
        json_response = response.json()
        logger.debug(f"🦙 Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

        llm_response = json_response.get("response")

        # Remove anything that looks like an HTML tag or is enclosed in angle brackets (even multiple brackets)
        if llm_response:
            llm_response = re.sub(r"<+[^>]+>+", "", llm_response)

        # Construct the ProxyResponse from the API response data.
        proxy_response = ProxyResponse(
            response=llm_response,
            generated_tokens=json_response.get("eval_count"),
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error parsing response from Ollama API: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid response format from Ollama API: {e}"
        )

    logger.debug(f"/discord/dm Response:\n{proxy_response.model_dump_json(indent=4)}")
    return proxy_response
