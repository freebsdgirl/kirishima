import httpx
import json

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

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
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    TIMEOUT = _config["timeout"]
    _ollama = _config["ollama"]

    url = f"{_ollama['server_url']}/api/show"
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