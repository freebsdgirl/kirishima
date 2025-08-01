"""
MCP email tool - Create email drafts via the googleapi service.

This module provides email functionality via the MCP (Model Context Protocol) service.
It only supports creating email drafts for review before sending, matching the existing
gmail tool functionality exactly.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any
import httpx
import os

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


async def email(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Create email drafts via MCP.
    Only supports 'send' action which creates drafts for safety.
    
    Args:
        action: The action to perform (only 'send' supported)
        to: Recipient email address
        subject: Email subject line
        content: Email body content
        from_email: Sender email address (optional)
        cc: CC recipient email address (optional)
    """
    try:
        action = parameters.get("action")
        if not action:
            return MCPToolResponse(success=False, result={}, error="Action is required")
        
        if action != "send":
            return MCPToolResponse(success=False, result={}, error=f"Error: Unsupported action '{action}'. Only 'send' is supported.")
        
        to = parameters.get("to")
        subject = parameters.get("subject")
        content = parameters.get("content")
        
        if not to or not subject or not content:
            return MCPToolResponse(success=False, result={}, error="to, subject, and content are required")
        
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
        from_email = parameters.get("from_email")
        if from_email:
            payload["from_email"] = from_email
            
        cc = parameters.get("cc")
        if cc:
            payload["cc"] = cc
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{googleapi_url}/gmail/draft", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                draft_id = result.get("data", {}).get("draft_id", "unknown")
                logger.info(f"Draft created successfully: {draft_id}")
                message = f"Email draft created successfully! Draft ID: {draft_id}. The email to '{to}' with subject '{subject}' has been saved as a draft for your review before sending."
                return MCPToolResponse(success=True, result={"status": "success", "message": message, "draft_id": draft_id})
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"Failed to create draft: {error_msg}")
                return MCPToolResponse(success=False, result={}, error=f"Failed to create email draft: {error_msg}")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating draft: {e.response.status_code} - {e.response.text}")
        return MCPToolResponse(success=False, result={}, error=f"Error creating email draft: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error creating draft: {e}")
        return MCPToolResponse(success=False, result={}, error=f"Error connecting to email service: {str(e)}")
    except Exception as e:
        logger.error(f"Error in email tool: {e}")
        return MCPToolResponse(success=False, result={}, error=str(e))
