"""
MCP smarthome tool - Smart home device control and automation via Home Assistant.

This module provides smart home functionality via the MCP (Model Context Protocol) service.
It supports natural language requests for controlling smart home devices including:
- Device discovery and matching based on natural language descriptions
- Action generation and execution via Home Assistant
- Media recommendations and control
- Lighting control with contextual awareness
- General device automation

The tool forwards requests to the smarthome service which handles device matching,
action generation, and execution through Home Assistant WebSocket API.
Returns standardized MCPToolResponse with action results and reasoning.
"""

from shared.models.mcp import MCPToolResponse
from shared.models.smarthome import UserRequest
from typing import Dict, Any
import httpx
import os
import json

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

# Smarthome service configuration
SMARTHOME_PORT = os.getenv("SMARTHOME_PORT", 4211)


def format_action_info(action: Dict[str, Any]) -> str:
    """
    Format action information into a compact, token-efficient string.
    
    Args:
        action: Action data from smarthome service
        
    Returns:
        str: Formatted action string
    """
    action_type = action.get('type', 'N/A')
    domain = action.get('domain', 'N/A')
    service = action.get('service', 'N/A')
    entity_id = action.get('entity_id', 'N/A')
    service_data = action.get('service_data', {})
    
    # Build formatted string
    parts = [f"Type: {action_type}", f"Service: {domain}.{service}"]
    
    if entity_id != 'N/A':
        parts.append(f"Entity: {entity_id}")
    
    if service_data:
        # Truncate service data if too long
        data_str = str(service_data)
        data_truncated = data_str[:100] + "..." if len(data_str) > 100 else data_str
        parts.append(f"Data: {data_truncated}")
    
    return " | ".join(parts)


async def smarthome(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Smart home control operations via MCP.
    Handles natural language requests for device control and automation.
    
    Parameters:
    - user_request (str): The full text request from the user
    - device (str, optional): The name of the specific device, if applicable
    """
    try:
        user_request = parameters.get("user_request")
        if not user_request:
            return MCPToolResponse(
                success=False, 
                result={}, 
                error="User request is required"
            )
        
        device = parameters.get("device")
        
        # Create the request data
        data = UserRequest(full_request=user_request, name=device)
        
        # Forward request to smarthome service
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f'http://smarthome:{SMARTHOME_PORT}/user_request',
                json=data.model_dump()
            )
            response.raise_for_status()
            result_data = response.json()
        
        # Check if the response indicates an error
        if "error" in result_data:
            return MCPToolResponse(
                success=False,
                result=result_data,
                error=result_data["error"]
            )
        
        # Format the response for better readability
        formatted_result = {
            "status": result_data.get("status", "unknown"),
            "message": result_data.get("message", ""),
            "reasoning": result_data.get("reasoning", ""),
        }
        
        # Handle different response types
        if "actions" in result_data:
            # Standard device control response
            actions = result_data["actions"]
            formatted_result["actions"] = actions
            formatted_result["action_count"] = len(actions)
            
            # Create compact action summaries
            if actions:
                formatted_result["action_summary"] = [
                    format_action_info(action) for action in actions
                ]
        
        elif "recommendations" in result_data:
            # Media recommendation response
            formatted_result["intent"] = result_data.get("intent", "")
            formatted_result["media_types"] = result_data.get("media_types", [])
            formatted_result["recommendations"] = result_data["recommendations"]
            formatted_result["device_ids"] = result_data.get("device_ids", [])
        
        # Determine success based on status
        success = result_data.get("status") == "success"
        error_msg = None if success else result_data.get("message", "Operation failed")
        
        return MCPToolResponse(
            success=success,
            result=formatted_result,
            error=error_msg
        )
        
    except httpx.TimeoutException:
        logger.error("Request to smarthome service timed out")
        return MCPToolResponse(
            success=False,
            result={},
            error="Request timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Request error when calling smarthome service: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Connection error: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from smarthome service: {e.response.status_code} - {e.response.text}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"HTTP {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error in smarthome MCP tool: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Unexpected error: {str(e)}"
        )
