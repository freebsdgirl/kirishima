"""
This module provides utility functions for interacting with language models (LLMs) and processing user messages.
Functions:
    - send_prompt_to_llm(prompt: str) -> dict:
        Sends a prompt to an Ollama language model and retrieves its response.
    - strip_to_last_user(messages: List[dict]) -> Optional[dict]:
        Extracts the last user message from a list of message dictionaries.
    - send_openai_payload_to_llm(payload: dict) -> dict:
        Placeholder function for sending OpenAI-compatible payloads to an LLM.
    - is_instruct_model(model_name: str) -> bool:
        Checks whether a given model uses an instruct-style format by querying the model's template.
Constants:
    - llm_model_name: The name of the default language model (retrieved from environment variables).
    - ollama_server_host: The hostname of the Ollama server (retrieved from environment variables).
    - ollama_server_port: The port number of the Ollama server (retrieved from environment variables).
"""

import app.config

from shared.log_config import get_logger
logger = get_logger(__name__)

from typing import List, Optional
import httpx


import os
llm_model_name = os.getenv('LLM_MODEL_NAME', 'nemo')
ollama_server_host = os.getenv('OLLAMA_SERVER_HOST', 'localhost')
ollama_server_port = os.getenv('OLLAMA_SERVER_PORT', '11434')


async def send_prompt_to_llm(prompt: str) -> dict:
    """
    Send a prompt to an Ollama language model and retrieve its response.
    
    Args:
        prompt (str): The input text prompt to send to the language model.
    
    Returns:
        dict: A dictionary containing the LLM's response with keys:
            - 'reply': The text response from the model
            - 'model': The name of the model used
            - 'raw': The full raw response data
            - 'error' (optional): Error details if the request fails
    
    Raises:
        httpx.HTTPError: If there's an HTTP-related error during the request.
    """
    logger.debug(f"Sending prompt to LLM: {prompt}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"http://{ollama_server_host}:{ollama_server_port}/api/generate",
                json={
                    "model": llm_model_name,
                    "prompt": prompt,
                    "stream": False,
                    "stop": ["<|im_end|>", "[USER]"]
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()
            return {
                "reply": data.get("response", ""),
                "model": llm_model_name,
                "raw": data
            }

    except Exception as e:
        logger.error(f"🔥 Failed to get response from Ollama: {e}")
        return {
            "reply": "[ERROR: Failed to get LLM response]",
            "error": str(e)
        }


def strip_to_last_user(messages: List[dict]) -> Optional[dict]:
    """
    Find and return the last user message from a list of messages.
    
    Args:
        messages (List[dict]): A list of message dictionaries.
    
    Returns:
        Optional[dict]: The last user message dictionary, or None if no user message is found.
    """
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg
    return None


async def send_openai_payload_to_llm(payload: dict) -> dict:
    """
    yeah, so, we're ripping this code out because ollama? actually kind of shit 
    at openai compatibilty with instruct models. lots of system prompt bleedthru.
    no thank u sir.
    """


async def is_instruct_model(model_name: str) -> bool:
    """
    Check whether a given model uses an instruct format by querying the /api/show endpoint.

    This function calls the service asynchronously to fetch the model's template and
    returns True if the template contains either "[INST]" or "<<SYS>>", indicating that
    it follows an instruct-style format.

    Args:
        model_name (str): The name of the model to check.

    Returns:
        bool: True if the instruct format is detected, False otherwise.
    """
    url = f"{app.config.OLLAMA_URL}/api/show"
    payload = {"model": model_name}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            template = data.get("template", "")
            return "[INST]" in template or "<<SYS>>" in template

        except Exception as exc:
            logger.warning(f"Failed to detect instruct format for model {model_name}: {exc}")
            return False
