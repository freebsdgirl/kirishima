"""
MCP (Model Context Protocol) routes for exposing Brain's tools and brainlets as standardized API endpoints.

This module implements the MCP server functionality, allowing external agents (like Copilot)
to discover and call Brain's tools in a standardized way.

Key endpoints:
- GET /mcp/tools - Dynamic tool discovery
- POST /mcp/memory_search - Ephemeral memory search
- POST /mcp/add_stickynote - Persistent stickynote creation
- POST /mcp/execute - Generic tool execution
"""

from fastapi import APIRouter, HTTPException
from shared.models.mcp import MCPToolsResponse, MCPToolRequest, MCPToolResponse
from app.services.mcp.registry import get_available_tools, is_tool_available
from app.services.mcp.memory_search import memory_search
from app.services.mcp.add_stickynote import add_stickynote

router = APIRouter()


@router.get("/tools", response_model=MCPToolsResponse)
async def get_tools():
    """
    Return the list of available tools and their schemas for dynamic discovery.
    This allows agents to discover what tools are available at runtime.
    """
    tools = get_available_tools()
    return MCPToolsResponse(tools=tools)


@router.post("/memory_search", response_model=MCPToolResponse)
async def mcp_memory_search(request: MCPToolRequest):
    """
    MCP endpoint for memory search. Calls the existing memory_search brainlet.
    This is an ephemeral tool - results are not logged to ledger.
    """
    return await memory_search(request.parameters)


@router.post("/add_stickynote", response_model=MCPToolResponse)
async def mcp_add_stickynote(request: MCPToolRequest):
    """
    MCP endpoint for adding sticky notes. This is a persistent tool.
    """
    return await add_stickynote(request.parameters)


@router.post("/execute", response_model=MCPToolResponse)
async def execute_tool(request: MCPToolRequest):
    """
    Generic tool execution endpoint. Routes to specific tool handlers based on tool_name.
    """
    tool_name = request.tool_name
    
    if not is_tool_available(tool_name):
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    # Route to specific tool handler
    if tool_name == "memory_search":
        return await memory_search(request.parameters)
    elif tool_name == "add_stickynote":
        return await add_stickynote(request.parameters)
    else:
        raise HTTPException(status_code=501, detail=f"Tool '{tool_name}' not implemented")
