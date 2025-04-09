"""
This module defines an API endpoint for handling incoming iMessage requests. It processes the requests 
using a prompt builder and sends the generated prompt to a language model (LLM) for a response.

Modules:
    - shared.models.proxy: Contains the ProxyRequest model used for request validation.
    - app.prompts.dispatcher: Provides the `get_prompt_builder` function to select the appropriate prompt builder.
    - app.util: Contains the `send_prompt_to_llm` function to send prompts to the LLM.
    - shared.log_config: Provides logging functionality.

Functions:
    - from_imessage(message: ProxyRequest) -> dict:
        Handles POST requests to the `/from/imessage` endpoint. Processes the incoming iMessage request 
        and returns a response containing the LLM's reply and raw response data.

Dependencies:
    - FastAPI: Used to define the API router and endpoint.
    - Logger: Used for logging debug information about incoming requests and LLM responses.
"""

from shared.models.proxy import ProxyRequest
from app.prompts.dispatcher import get_prompt_builder
from app.util import send_prompt_to_llm

from shared.log_config import get_logger
logger = get_logger(__name__)

from fastapi import APIRouter


router = APIRouter()


@router.post("/from/imessage", response_model=dict)
async def from_imessage(message: ProxyRequest) -> dict:
    """
    Handle incoming iMessage requests by processing the message through a prompt builder and sending it to an LLM.

    Args:
        message (ProxyRequest): The incoming iMessage request containing mode and memories.

    Returns:
        dict: A response containing the status, LLM reply, and raw response data.
    """
    logger.debug(f"Received iMessage request: {message}")

    # 1. Use dispatcher to pick correct builder
    builder = get_prompt_builder(message.mode, message.memories)

    # 2. Call the selected builder with full ProxyRequest
    prompt = builder(message)

    # 3. Log or return the prompt (for now)
    response = await send_prompt_to_llm(prompt)

    logger.debug(f"LLM response: {response}")

    return {
        "status": "success",
        "reply": response.get("reply", ""),
        "raw": response.get("raw")
    }
