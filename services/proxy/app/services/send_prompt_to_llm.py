from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
import json


async def _send_prompt_to_llm(prompt: str) -> dict:
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

    with open('/app/config/config.json') as f:
        _config = json.load(f)
    TIMEOUT = _config["timeout"]
    _ollama = _config["ollama"]

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"http://{_ollama['server_url']}/api/generate",
                json={
                    "model": _ollama['model_name'],
                    "prompt": prompt,
                    "stream": False,
                    "stop": ["<|im_end|>", "[USER]"]
                }
            )

            response.raise_for_status()
            data = response.json()
            return {
                "reply": data.get("response", ""),
                "model": _ollama['model_name'],
                "raw": data
            }

    except Exception as e:
        logger.error(f"🔥 Failed to get response from Ollama: {e}")
        return {
            "reply": "[ERROR: Failed to get LLM response]",
            "error": str(e)
        }