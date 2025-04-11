"""
API endpoint for handling chat completions in an OpenAI-compatible format.

This endpoint processes chat requests, generates completions using a generative AI model,
and supports multiple retry attempts to ensure a meaningful response. It handles both 
/v1/chat/completions and /chat/completions routes.

Attributes:
    max_attempts (int): Maximum number of attempts to generate a valid response.
    request_data (ChatRequest): Request containing messages, model settings, and generation parameters.

Returns:
    dict: A response object containing the generated chat completion, following OpenAI's response format.
"""
import app.config

from shared.log_config import get_logger
logger = get_logger(__name__)

from app.v1.chat.buffer import add_to_buffer
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import re

# Define the structure of an OpenAI-style chat request
class ChatRequest(BaseModel):
    """
    Pydantic model representing an OpenAI-compatible chat completion request.
    
    Attributes:
        messages (list): A list of message objects representing the conversation history.
        model (str, optional): The name of the language model to use. Defaults to the configured default model.
        temperature (float, optional): Controls randomness in generation. Defaults to the configured default temperature.
        top_p (float, optional): Controls diversity of token selection. Defaults to the configured default top_p value.
        stream (bool, optional): Indicates whether to stream the response. Defaults to the configured default streaming setting.
    """
    messages: list
    model: str = app.config.DEFAULT_SETTINGS['model'] 
    temperature: float = app.config.DEFAULT_SETTINGS['temperature']
    top_p: float = app.config.DEFAULT_SETTINGS['top_p']
    stream: bool = app.config.DEFAULT_SETTINGS['stream'] 


router = APIRouter()
app = FastAPI()


# genie vs code is demanding a /v1 prefix for some godawful reason
@router.post("/v1/chat/completions")
async def v1_chat_completions(request_data: ChatRequest):
    """
    Handle chat completions for the /v1/chat/completions API endpoint.

    Forwards the request to the main chat_completions handler, providing compatibility
    with the /v1 route prefix required by some clients.

    Args:
        request_data (ChatRequest): The chat completion request containing messages and model parameters.

    Returns:
        JSONResponse: A response containing the generated chat completion.
    """
    return await chat_completions(request_data)


@router.post("/chat/completions")
async def chat_completions(request_data: ChatRequest):
    """
    Handle chat completions by generating a response from the language model.

    Attempts to generate a valid completion up to a maximum number of attempts.
    Filters out invalid or empty responses. Adds both user and model messages to a buffer.

    Args:
        request_data (ChatRequest): The chat completion request containing messages and model parameters.

    Returns:
        JSONResponse: A response containing the generated chat completion with a 200 status code.
    """
    from .generate import generate_completion

    max_attempts = app.config.CHAT_COMPLETIONS_MAX_ATTEMPTS
    attempt = 0
    response = None
    response_text = None

    # add the user message to buffer

    while attempt < max_attempts:
        response = await generate_completion(request_data)
        response_text = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if response_text and len(response_text) > 5 and response_text not in {"[TOOL_CALLS]","```", "😏", ">>>", "___"}:
            break

        attempt += 1

    # add the llm message to buffer
    add_to_buffer(response_text, 'Kirishima')

    return JSONResponse(content=response, status_code=200)
