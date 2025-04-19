"""
This module provides utility functions for interacting with a language model service 
and processing memory entries. It includes functions to send prompts to the language 
model, check if a model uses an instruct format, and create a string representation 
of memory entries.
Functions:
    - send_prompt_to_llm(prompt: str) -> dict:
        Sends a prompt to the language model and retrieves its response.
    - is_instruct_model(model_name: str) -> bool:
        Checks if a given model uses an instruct-style format by querying the service.
    - create_memory_str(memories: List[MemoryEntryFull]) -> str:
"""

import app.config

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
from typing import List
from shared.models.chromadb import MemoryEntryFull

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
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"http://{app.config.OLLAMA_URL}/api/generate",
                json={
                    "model": app.config.LLM_MODEL_NAME,
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
                "model": app.config.LLM_MODEL_NAME,
                "raw": data
            }

    except Exception as e:
        logger.error(f"🔥 Failed to get response from Ollama: {e}")
        return {
            "reply": "[ERROR: Failed to get LLM response]",
            "error": str(e)
        }


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

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            template = data.get("template", "")
            return "[INST]" in template or "<<SYS>>" in template

        except Exception as exc:
            logger.warning(f"Failed to detect instruct format for model {model_name}: {exc}")
            return False


def create_memory_str(memories: List[MemoryEntryFull]) -> str:
    """
    Converts a list of memory entries into a single string representation.
    
    Args:
        memories (List[MemoryEntryFull]): A list of memory entries to be converted.
    
    Returns:
        str: A single string with memory entries joined by newlines, in reverse order.
    """
    return "\n".join([f" - {m.memory}" for m in reversed(memories)])