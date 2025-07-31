"""
Shared models for MCP (Model Context Protocol) server functionality.
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class MCPToolSchema(BaseModel):
    """Schema definition for an MCP tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    returns: Dict[str, Any]


class MCPToolsResponse(BaseModel):
    """Response model for tool discovery endpoint."""
    tools: List[MCPToolSchema]


class MCPToolRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    parameters: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


class MCPToolResponse(BaseModel):
    """Response model for tool execution."""
    success: bool
    result: Any
    error: Optional[str] = None
