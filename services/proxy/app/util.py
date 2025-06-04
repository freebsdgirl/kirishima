"""
This module provides utility functions for interacting with a language model (LLM), 
building prompts, and managing memory entries. It includes functions for sending 
prompts to the LLM, checking model formats, creating memory strings, and dynamically 
selecting prompt builders based on modes.
Functions:
- send_prompt_to_llm(prompt: str) -> dict:
    Sends a prompt to the LLM and retrieves its response.
- is_instruct_model(model_name: str) -> bool:
    Checks if a given model uses an instruct-style format by querying its template.
- create_memory_str(memories: List[MemoryEntryFull]) -> str:
- build_multiturn_prompt(request: ChatMessages, system_prompt: str) -> str:
    Builds a multi-turn prompt for an instruct-style LLM using chat messages and a system prompt.
- get_prompt_builder(mode: str = None):
- get_system_prompt(request):
    Determines and generates the appropriate system prompt based on the request mode.
- resolve_model_provider_options(mode: str):
    Returns the provider, model, and options for the given mode.
Dependencies:
- app.config: Configuration settings for the application.
- shared.config: Shared configuration settings, including TIMEOUT.
- shared.log_config: Logging configuration for the application.
- httpx: HTTP client for making asynchronous requests.
- shared.models.memory: Memory entry model definitions.
- shared.models.proxy: Chat message model definitions.
- app.prompts: Modules for building prompts based on different modes.
Logging:
- Uses a logger instance to log debug, error, and warning messages.
Exceptions:
- Handles HTTP and general exceptions during LLM interactions and logs errors or warnings.

"""
import app.config

from shared.models.memory import MemoryEntryFull

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
from typing import List
import json

with open('/app/shared/config.json') as f:
    _config = json.load(f)
TIMEOUT = _config["timeout"]


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
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"http://{app.config.OLLAMA_URL}/api/generate",
                json={
                    "model": app.config.LLM_MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "stop": ["<|im_end|>", "[USER]"]
                }
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

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
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
    return "\n".join([f" - {m.memory}" for m in reversed(memories)])\


def build_multiturn_prompt(messages: list, system_prompt: str, provider: str = None) -> str:
    """
    Builds a multi-turn prompt for a language model using the specified chat messages and system prompt.
    Provider-specific formatting is applied (e.g., OpenAI vs. Ollama/instruct style).
    Args:
        messages (list): The sequence of chat messages (dicts) to be formatted.
        system_prompt (str): The initial system-level instruction for the model.
        provider (str, optional): The provider (e.g., 'openai', 'ollama').
    Returns:
        str: A formatted multi-turn prompt compatible with the provider's requirements.
    """
    if provider == "openai":
        # For OpenAI, the prompt is handled via the messages list, so just return system_prompt for logging/debug
        return system_prompt
    # Default: Ollama/instruct style
    prompt_header = f"[INST] <<SYS>>{system_prompt}<</SYS>> [/INST]\n\n"
    prompt = prompt_header
    for m in messages:
        if m["role"] == "system":
            prompt += f"[INST] <<SYS>>{m['content']}<</SYS>> [/INST]\n"
        elif m["role"] == "user":
            prompt += f"[INST] {m['content']} [/INST]"
        elif m["role"] == "assistant":
            prompt += f" {m['content']}\n"
    return prompt


def resolve_model_provider_options(mode: str):
    """
    Given a mode string, return (provider, model, options) for the LLM.
    Looks up the mode in the loaded config. If not found, falls back to 'default'.
    Returns:
        provider (str): e.g. 'openai', 'ollama'
        model (str): actual model name for the provider
        options (dict): provider-specific options (temperature, max_tokens, etc.)
    Raises:
        ValueError: If provider is missing from the config for the mode.
    """
    llm_modes = _config.get("llm", {}).get("mode", {})
    mode_config = llm_modes.get(mode) or llm_modes.get("default")
    if not mode_config:
        raise ValueError(f"No config found for mode '{mode}' and no default mode present.")
    provider = mode_config.get("provider")
    if not provider:
        raise ValueError(f"No provider specified for mode '{mode}'. Please specify a provider in config.")
    model = mode_config.get("model")
    options = mode_config.get("options", {})
    return provider, model, options