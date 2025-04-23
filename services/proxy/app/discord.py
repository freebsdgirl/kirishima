from shared.models.proxy import ProxyDiscordDMRequest, ProxyResponse, ProxyRequest, IncomingMessage
from shared.models.discord import DiscordDirectMessage
from shared.models.contacts import Contact

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import app.config

import httpx
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

async def get_prompt_builder(mode: str = None):
    if mode:
        if mode == "nsfw":
            from app.prompts.nsfw.generate import build_prompt

        elif mode == "work":
            from app.prompts.work.generate import build_prompt

        elif mode == "guest":
            from app.prompts.guest.generate import build_prompt

        else:
            from app.prompts.default.generate import build_prompt

    else:
        from app.prompts.guest.generate import build_prompt

    return build_prompt


def build_multiturn_prompt(request: ProxyDiscordDMRequest, system_prompt: str) -> str:
    # 1) System prompt header
    prompt_header = f"[INST] <<SYS>>{system_prompt}<</SYS>> [/INST]\n\n"
    max_history_tokens = 1024
    
    prompt = prompt_header

    for m in request.messages:
        if m.role == "system":
            prompt += f"[INST] <<SYS>>{m.content}<</SYS>> [/INST]\n"
        elif m.role == "user":
            prompt += f"[INST] {m.content} [/INST]"
        else:
            prompt += f" {m.content}\n"

    return prompt


@router.post("/discord/dm")
async def discord_dm(request: ProxyDiscordDMRequest):
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

    # fetch the builder function
    build_sys = await get_prompt_builder(request.mode)

    # assemble a minimal ProxyRequest just to generate the system prompt
    # it only needs .message, .user_id, .context, .mode, .memories
    proxy_req = ProxyRequest(
        message=IncomingMessage(
            platform="discord", 
            sender_id=request.contact.id,
            text=request.message.content,
            timestamp=request.message.timestamp,
            metadata={}
        ),
        user_id=request.contact.id,
        context=request.message.display_name,
        mode=request.mode,
        memories=request.memories,
        summaries=request.summaries
    )
    
    # now get your dynamic system prompt
    system_prompt = build_sys(proxy_req)

    # 4) build the full instruct‑style prompt
    full_prompt = build_multiturn_prompt(request, system_prompt)

    # Construct the payload for the Ollama API call
    payload = {
        "model": 'nemo:latest',
        "prompt": full_prompt,
        "temperature": 0.3,
        "max_tokens": 256,
        "stream": False,
        "raw": True
    }

    logger.debug(f"Request to Ollama API:\n{json.dumps(payload, indent=4, ensure_ascii=False)}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=60) as client:
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

    json_response = response.json()
    logger.debug(f"Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    # Construct the ProxyResponse from the API response data.
    proxy_response = ProxyResponse(
        response=json_response.get("response"),
        generated_tokens=json_response.get("eval_count"),
        timestamp=datetime.now().isoformat()
    )

    logger.debug(f"/discord/dm Response:\n{proxy_response.model_dump_json(indent=4)}")
    return proxy_response
