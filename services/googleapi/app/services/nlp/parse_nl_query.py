"""
This module provides functionality to parse natural language queries into structured actions
for Google API services using a language model (LLM) via a proxy service.
Functions:
    parse_natural_language_query(query: str) -> GoogleServiceAction:
        Asynchronously sends a natural language query to an LLM for parsing into a structured
        GoogleServiceAction object. Handles prompt construction, communication with the proxy
        service, response validation, and error handling.
Dependencies:
    - httpx: For asynchronous HTTP requests.
    - datetime: For timestamping prompts.
    - os: For environment variable access.
    - shared.models.proxy.SingleTurnRequest: For request modeling.
    - shared.models.googleapi.GoogleServiceAction: For structured action modeling.
    - shared.prompt_loader.load_prompt: For prompt template loading.
    - shared.log_config.get_logger: For logging.
"""
import json
import httpx
from datetime import datetime, timezone

from shared.models.proxy import SingleTurnRequest
from shared.models.googleapi import (
    GoogleServiceAction
)
from shared.prompt_loader import load_prompt

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

import os

TIMEOUT = 30.0


async def parse_natural_language_query(query: str) -> GoogleServiceAction:
    """
    Send a natural language query to LLM for parsing into structured action.
    
    Args:
        query: Natural language query from user
        
    Returns:
        GoogleServiceAction: Parsed action with service, action, and parameters
        
    Raises:
        HTTPException: If LLM parsing fails or returns invalid response
    """
    try:
        # Get current datetime for the prompt
        current_datetime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Load the prompt template with current datetime
        prompt = load_prompt("googleapi", "nlp", "action_parser", 
                            query=query, 
                            current_datetime=current_datetime)
        
        # Create request for proxy service
        singleturn_request = SingleTurnRequest(
            model="email",
            prompt=prompt
        )
        
        # Send to proxy service
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            proxy_port = os.getenv("PROXY_PORT", 4205)
            response = await client.post(
                f"http://proxy:{proxy_port}/api/singleturn",
                json=singleturn_request.model_dump()
            )
            response.raise_for_status()
            
        proxy_response = response.json()
        llm_response = proxy_response.get("response", "").strip()
        
        logger.debug(f"LLM response for query '{query}': {llm_response}")
        
        # Add more detailed logging
        if not llm_response:
            logger.error(f"Empty LLM response for query: {query}")
            return {
                "status": "error",
                "message": "LLM returned empty response"
            }
        
        # Parse JSON response
        try:
            action_data = json.loads(llm_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: '{llm_response}' for query: '{query}'")
            return {
                "status": "error",
                "message": f"LLM returned invalid JSON: {str(e)}"
            }

        # Validate required fields
        if not all(key in action_data for key in ["service", "action", "parameters"]):
            return {
                "status": "error",
                "message": "LLM response missing required fields (service, action, parameters)"
            }
            
        return GoogleServiceAction(**action_data)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from proxy service: {e.response.status_code} - {e.response.text}")
        return {
            "status": "error",
            "message": f"Error from LLM service: {e.response.text}"
        }
    except httpx.RequestError as e:
        logger.error(f"Request error to proxy service: {e}")
        return {
            "status": "error",
            "message": f"Request failed: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error parsing query '{query}': {e}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }