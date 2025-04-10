"""
This module provides functionality for handling multi-turn conversations with a language model 
via a FastAPI endpoint. It includes utilities for constructing instruct-style prompts and 
interacting with the Ollama API.
Functions:
    build_multiturn_prompt(request: ProxyMultiTurnRequest, system_prompt: str) -> str:
        Constructs a raw, instruct-style prompt for a multi-turn conversation based on 
        the provided conversation history and a system prompt.
    from_api_multiturn(request: ProxyMultiTurnRequest) -> ProxyResponse:
        FastAPI endpoint for handling multi-turn proxy interactions with a language model. 
        It validates the model's compatibility, constructs a formatted prompt, sends a request 
        to the Ollama API, and returns the response.
Dependencies:
    - app.config: Configuration settings for the application.
    - app.util.is_instruct_model: Utility to check if a model supports instruct-style prompts.
    - shared.models.proxy.ProxyMultiTurnRequest: Data model for multi-turn requests.
    - shared.models.proxy.ProxyResponse: Data model for API responses.
    - shared.log_config.get_logger: Logger configuration.
    - httpx: Async HTTP client for API communication.
    - fastapi: Framework for building the API endpoint.
"""

import app.config

from app.util import is_instruct_model
from app.prompts.basic import system_prompt

from shared.models.proxy import ProxyMultiTurnRequest, ProxyResponse

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


def build_multiturn_prompt(request: ProxyMultiTurnRequest, system_prompt: str) -> str:
    """
    Builds a raw, instruct-style prompt for a multi-turn conversation.
    
    The prompt is constructed using the following template:
    
      [INST] <<SYS>>{system_prompt}<<SYS>> [/INST]
      
      [INST] user message 1 [/INST] assistant reply 1
      [INST] user message 2 [/INST] assistant reply 2
      [INST] user message 3 [/INST]
      
    Args:
        request (ProxyMultiTurnRequest): The request containing conversation messages.
        system_prompt (str): A placeholder system prompt to be injected.
    
    Returns:
        str: The fully formatted multi-turn prompt.
    """
    # Start with the system message block
    prompt = f"[INST] <<SYS>>{system_prompt}<<SYS>> [/INST]\n\n"
    
    messages = request.messages
    num_messages = len(messages)

    # Build the conversation turns.
    # We expect that turns alternate: a user message (wrapped) optionally followed by an assistant reply.
    i = 0
    while i < num_messages:
        # Check that the current message is from user
        if messages[i].role != "user":
            logger.warning(f"Unexpected message role at position {i}: expected 'user', got '{messages[i].role}'.")
            # Skip non-user messages or optionally raise an error.
            i += 1
            continue

        # Wrap the user message in [INST] tags.
        prompt += f"[INST] {messages[i].content} [/INST]"

        # Look ahead for an assistant reply
        if (i + 1 < num_messages) and (messages[i + 1].role == "assistant"):
            prompt += f" {messages[i + 1].content}\n"
            i += 2
        else:
            # No assistant reply found, meaning this is the last user message prompting a response.
            prompt += "\n"
            i += 1

    return prompt


@router.post("/from/api/multiturn", response_model=ProxyResponse)
async def from_api_multiturn(request: ProxyMultiTurnRequest) -> ProxyResponse:
    """
    Handles multi-turn proxy interactions with an LLM by constructing an instruct‑style raw prompt 
    from conversation history and sending it to the Ollama API.
    
    This endpoint performs the following steps:
    
    1. Uses `is_instruct_model` to verify that the specified model supports the instruct format.
       If it does not, returns a 404.
    2. Constructs an instruct‑style prompt for multi‑turn conversations using a pre‑defined system prompt 
       placeholder and the conversation history. The formatting follows the template:
       
          [INST] <<SYS>>{system_prompt}<<SYS>> [/INST]
          
          [INST] user message [/INST] assistant reply
          [INST] user message [/INST] 
       
       where the final unpaired [INST] block indicates that it's the model's turn.
    3. Creates a payload for the Ollama API with `raw: true` and `stream: false`, then sends the request.
    4. Parses the API response and returns a `ProxyResponse`.
    
    Args:
        request (ProxyMultiTurnRequest): The multi-turn request containing model, conversation messages, 
                                           temperature, and max tokens.
    
    Returns:
        ProxyResponse: The response from the LLM, including generated text, token usage, and a timestamp.
    
    Raises:
        HTTPException: If the model is not instruct‑compatible or if there are errors communicating with the API.
    """
    logger.debug(f"Received multi-turn proxy request: {request}")

    # Check if the model supports instruct formatting.
    if not await is_instruct_model(request.model):
        logger.error(f"Model '{request.model}' is not instruct compatible.")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{request.model}' is not instruct compatible."
        )

    # Construct the multi-turn prompt using raw formatting.
    formatted_prompt = build_multiturn_prompt(request, system_prompt)
    logger.debug(f"Constructed multi-turn prompt: {formatted_prompt}")

    # Construct the payload for the Ollama API call
    payload = {
        "model": request.model,
        "prompt": formatted_prompt,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": False,
        "raw": True
    }

    logger.debug(f"Payload for Ollama API (multi-turn): {payload}")

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
    logger.debug(f"Response from Ollama API (multi-turn): {json_response}")

    # Construct the ProxyResponse from the API response data.
    proxy_response = ProxyResponse(
        response=json_response.get("response"),
        generated_tokens=json_response.get("eval_count"),
        timestamp=datetime.now().isoformat()
    )

    logger.debug(f"Returning multi-turn proxy response: {proxy_response}")
    return proxy_response
