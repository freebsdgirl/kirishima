"""
API module for handling requests to the proxy service.

This module defines an endpoint for processing requests from the API. It uses
a prompt builder to construct system prompts, extracts user messages, and sends
payloads to a language model for generating responses.

Functions:
    from_api(message: ProxyRequest) -> dict:
        Handles POST requests to the "/from/api" endpoint. Processes the input
        message, constructs a system prompt, extracts the last user message,
        builds a payload, and sends it to the language model for a response.

Dependencies:
    - shared.models.proxy.ProxyRequest: Defines the structure of the incoming
      request payload.
    - app.prompts.dispatcher.get_prompt_builder: Retrieves the appropriate
      prompt builder based on the mode and memories.
    - app.util.send_openai_payload_to_llm: Sends the constructed payload to the
      language model and retrieves the response.
    - app.util.strip_to_last_user: Extracts the last user message from a list
      of messages.
    - shared.log_config.get_logger: Configures and retrieves the logger for
      logging debug and error messages.
    - fastapi.APIRouter: Used to define the API route.

Environment Variables:
    - LLM_MODEL_NAME: Specifies the name of the language model to use. Defaults
      to 'nemo' if not set.

Routes:
    POST /from/api:
        Processes a ProxyRequest payload and returns a response containing the
        language model's reply and raw output.

"""

from shared.models.proxy import ProxyRequest

from app.prompts.dispatcher import get_prompt_builder
from app.util import send_openai_payload_to_llm, strip_to_last_user

from shared.log_config import get_logger
logger = get_logger(__name__)


from fastapi import APIRouter
router = APIRouter()


import os
llm_model_name = os.getenv('LLM_MODEL_NAME', 'nemo')


@router.post("/from/api", response_model=dict)
async def from_api(message: ProxyRequest) -> dict:
    """
    Handles POST requests to the "/from/api" endpoint by processing a ProxyRequest.

    Constructs a system prompt, extracts the last user message, builds an OpenAI-compatible
    payload, and sends it to a language model. Returns a dictionary with the response status,
    generated reply, and raw output.

    Args:
        message (ProxyRequest): The incoming request containing mode, memories, and message metadata.

    Returns:
        dict: A response containing 'status', 'reply', and optional 'raw' keys from the language model.
        Returns an error dictionary if message validation fails.
    """
    logger.debug(f"Received API request: {message}")

    # Step 1: Build the system prompt
    builder = get_prompt_builder(message.mode, message.memories)
    system_prompt = builder(message)
    logger.debug(f"Constructed system prompt: {system_prompt}")

    # Step 2: Extract OpenAI-style messages
    messages = message.message.metadata.get("messages")
    if not isinstance(messages, list):
        logger.error("Invalid or missing 'messages' in metadata.")

        return {
            "error": "Invalid or missing 'messages' list in metadata."
        }

    # Step 3: Get last user message
    last_user_msg = strip_to_last_user(messages)
    if not last_user_msg:
        logger.error("No user message found in 'messages'.")

        return {
            "error": "No user message found in 'messages'."
        }

    logger.debug(f"Last user message: {last_user_msg}")

    # Step 4: Build OpenAI payload
    payload = {
        "model": llm_model_name,
        "messages": [
            {
                "role": "system", "content": system_prompt
            },
            last_user_msg
        ]
    }

    logger.debug(f"Sending payload to LLM: {payload}")

    # Step 5: Send to LLM
    response =  await send_openai_payload_to_llm(payload)
    logger.debug(f"LLM response: {response}")

    return {
        "status": "success",
        "reply": response.get("reply", ""),
        "raw": response.get("raw")
    }