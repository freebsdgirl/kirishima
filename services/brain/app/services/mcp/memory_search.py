"""
Memory search service for MCP.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any


async def memory_search(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Execute memory search via MCP.
    This is an ephemeral tool - results are not logged to ledger.
    """
    try:
        # Import here to avoid circular imports
        from app.brainlets.memory_search import memory_search as brainlet_memory_search
        
        query = parameters.get("query")
        limit = parameters.get("limit", 10)
        
        if not query:
            return MCPToolResponse(success=False, error="Query parameter is required")
        
        # Call the existing memory_search brainlet
        result = await brainlet_memory_search(query, limit)
        
        return MCPToolResponse(success=True, result=result)
    
    except Exception as e:
        return MCPToolResponse(success=False, error=str(e))
