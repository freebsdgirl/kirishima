"""
This module provides an API endpoint to retrieve detailed information about AI models 
from the Ollama API. It includes fine-tuning tracking data for specific models.

Modules:
    - fastapi: Used to create the API router and handle HTTP exceptions.
    - requests: Used to make HTTP requests to the Ollama API.
    - datetime: Used to handle timestamps for fine-tuned model files.
    - os: Used to check the existence and modification time of the model file.
    - log_config: Custom module to configure logging.

Constants:
    - OLLAMA_API_URL (str): The base URL for the Ollama API.
    - model_path (str): The file path to the fine-tuned model file.
    - FINE_TUNING_LOG (dict): A dictionary containing fine-tuning metadata for models.

Functions:
    - get_model(model_id: str): An asynchronous endpoint to retrieve model details 
      including name, parameters, context length, quantization, and fine-tuning information.

Attributes:
    - router (APIRouter): The FastAPI router instance for defining API routes.
    - logger: Logger instance for logging debug and error messages.
"""
from fastapi import APIRouter, HTTPException

import requests
from datetime import datetime
import os

from shared.log_config import get_logger
logger = get_logger(__name__)


router = APIRouter()

OLLAMA_API_URL = "http://localhost:11434/api/show"


# Path to the fine-tuned model file
model_path = "/home/randi/.ollama/models/nemo/adapter_model.safetensors"

# Check if the file exists before accessing timestamp
if os.path.exists(model_path):
    timestamp = datetime.fromtimestamp(os.path.getmtime(model_path)).isoformat()
else:
    timestamp = "File not found"

# Realistic fine-tuning tracking data
FINE_TUNING_LOG = {
    "nemo": {
        "fine_tuned_on": timestamp,
        "dataset_files": [
            "20250308.json"
        ],
        "epochs": 5,
        "base_model": "Nemo-Instruct:12B",
        "adapter": "LoRA",
        "quantization": "Q_4",
        "description": "Fine-tuned for immersive roleplay, banter, and explicit interactions."
    }
}


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """
    Retrieve detailed information about a specific AI model from the Ollama API.

    Args:
        model_id (str): The unique identifier of the model to retrieve.

    Returns:
        dict: A dictionary containing model details including name, parameters, 
            context length, quantization, and fine-tuning information.

    Raises:
        HTTPException: If there is an error retrieving or processing the model information.
    """
    try:
        # Log request if debug mode is enabled
        logger.debug(f"🔹 Model Requested: {model_id}")

        response = requests.get(f"{OLLAMA_API_URL}/{model_id}")
        model_data = response.json()

        # Log response if debug mode is enabled
        logger.debug(f"🔹 Model Data: {model_data}")

        # Retrieve fine-tuning details if available
        fine_tuning_data = FINE_TUNING_LOG.get(model_id, {})

        return {
            "model": model_data.get("model", "Unknown"),
            "parameters": model_data.get("parameters", "Unknown"),
            "context_length": model_data.get("context_length", "Unknown"),
            "quantization": model_data.get("quantization", "Unknown"),
            "fine_tuning": fine_tuning_data,
        }

    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
