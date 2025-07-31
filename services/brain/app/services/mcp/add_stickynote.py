"""
Sticky notes service for MCP.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any


async def add_stickynote(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Create a sticky note via MCP.
    This is a persistent tool - writes to ledger.
    """
    try:
        content = parameters.get("content")
        priority = parameters.get("priority", "medium")
        
        if not content:
            return MCPToolResponse(success=False, error="Content parameter is required")
        
        # TODO: Implement actual stickynotes API call
        # This should call the stickynotes service
        result = {
            "note_id": "stub_note_id",
            "status": "created",
            "content": content,
            "priority": priority
        }
        
        return MCPToolResponse(success=True, result=result)
    
    except Exception as e:
        return MCPToolResponse(success=False, error=str(e))
