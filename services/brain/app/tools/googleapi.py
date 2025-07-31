"""
"""

import os
import json
import httpx

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


def googleapi_nlp(query: str):
    """
    Send a query to the Google API NLP service.
    
    """
    
    # Get googleapi service port from environment
    
    # Prepare request payload for the draft endpoint
    payload = {
        "query": query
    }
        
    try:
        # Make request to googleapi service to create draft
        with httpx.Client(timeout=30.0) as client:
            googleapi_port = os.getenv("GOOGLEAPI_PORT", 4215)
            response = client.post(f"http://googleapi:{googleapi_port}/nlp?readable=true", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("success"):
                action_taken = data.get("action_taken", {})
                result = data.get("result", {})

                if (
                    action_taken.get("action") == "search_contacts"
                    or action_taken.get("action") == "search_events"
                    or action_taken.get("action") == "list_events"
                ):
                    result = data.get("result", {}).get("result")
                    return {"status": "ok", "data": result}
                
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating draft: {e.response.status_code} - {e.response.text}")
        return f"Error creating email draft: HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"Request error creating draft: {e}")
        return f"Error connecting to email service: {e}"
    except Exception as e:
        logger.error(f"Unexpected error creating draft: {e}")
        return f"Unexpected error creating email draft: {e}"
