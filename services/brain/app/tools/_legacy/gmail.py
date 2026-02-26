"""
Gmail tool for sending emails via the googleapi service.

Note: This tool creates email drafts for review before sending,
providing a safety mechanism for AI-generated emails.
"""

import os
import json
import httpx
from shared.log_config import get_logger

logger = get_logger(f"brain.tools.{__name__}")


def gmail(action: str, to: str, subject: str, content: str, from_email: str = None, cc: str = None, **kwargs) -> str:
    """
    Send an email via Gmail (creates draft for review).
    
    Args:
        action: The action to perform (currently only 'send')
        to: Recipient email address
        subject: Email subject line
        content: Email body content
        from_email: Sender email address (optional)
        cc: CC recipient email address (optional)
        **kwargs: Additional arguments (ignored)
        
    Returns:
        str: Success or error message
    """
    if action != "send":
        return f"Error: Unsupported action '{action}'. Only 'send' is supported."
    
    # Get googleapi service port from environment
    googleapi_port = os.getenv("GOOGLEAPI_PORT", 4215)
    googleapi_url = f"http://googleapi:{googleapi_port}"
    
    # Prepare request payload for the draft endpoint
    payload = {
        "to": to,
        "subject": subject,
        "body": content
    }
    
    # Add optional fields if provided
    if from_email:
        payload["from_email"] = from_email
    if cc:
        payload["cc"] = cc
    
    try:
        # Make request to googleapi service to create draft
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{googleapi_url}/gmail/draft", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                draft_id = result.get("data", {}).get("draft_id", "unknown")
                logger.info(f"Draft created successfully: {draft_id}")
                return f"Email draft created successfully! Draft ID: {draft_id}. The email to '{to}' with subject '{subject}' has been saved as a draft for your review before sending."
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"Failed to create draft: {error_msg}")
                return f"Failed to create email draft: {error_msg}"
                
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating draft: {e.response.status_code} - {e.response.text}")
        return f"Error creating email draft: HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"Request error creating draft: {e}")
        return f"Error connecting to email service: {e}"
    except Exception as e:
        logger.error(f"Unexpected error creating draft: {e}")
        return f"Unexpected error creating email draft: {e}"
