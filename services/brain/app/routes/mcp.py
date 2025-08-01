"""
MCP (Model Context Protocol) routes for exposing Brain's tools and brainlets as standardized API endpoints.

This module implements the MCP server functionality, allowing external agents (like Copilot)
to discover and call Brain's tools in a standardized way.

Key endpoints:
- GET /mcp/tools - Dynamic tool discovery
- POST /mcp/memory - Comprehensive memory management (search, create, update, delete, list, get)
- POST /mcp/github_issue - GitHub issue management (create, view, comment, close, list)
- POST /mcp/execute - Generic tool execution with dependency resolution
- GET /mcp/validate - Dependency validation
"""

from fastapi import APIRouter, HTTPException
from shared.models.mcp import MCPToolsResponse, MCPToolRequest, MCPToolResponse
from app.services.mcp.registry import (
    get_available_tools, 
    get_available_tools_for_client,
    is_tool_available, 
    is_tool_available_for_client,
    _load_tool_registry
)
from app.services.mcp.executor import execute_tool_with_dependencies
from app.services.mcp.dependencies import validate_all_dependencies

router = APIRouter()


@router.post("/")
async def mcp_handler(request: dict):
    """
    Main MCP protocol handler for JSON-RPC requests.
    """
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "kirishima-brain",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        tools = get_available_tools()
        return {
            "jsonrpc": "2.0", 
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.parameters
                    } for tool in tools
                ]
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not is_tool_available(tool_name):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found"
                }
            }
        
        tool_registry = _load_tool_registry()
        result = await execute_tool_with_dependencies(tool_name, arguments, tool_registry)
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": str(result.result) if result.success else result.error
                    }
                ],
                "isError": not result.success
            }
        }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id, 
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found"
            }
        }


@router.post("/copilot/")
async def mcp_copilot_handler(request: dict):
    """
    MCP protocol handler for GitHub Copilot with filtered tools.
    Same protocol as main MCP endpoint but with restricted tool access.
    """
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "kirishima-brain-copilot",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        tools = get_available_tools_for_client("copilot")
        return {
            "jsonrpc": "2.0", 
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.parameters
                    } for tool in tools
                ]
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not is_tool_available_for_client(tool_name, "copilot"):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found or not authorized for Copilot"
                }
            }
        
        tool_registry = _load_tool_registry()
        result = await execute_tool_with_dependencies(tool_name, arguments, tool_registry)
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": str(result.result) if result.success else result.error
                    }
                ],
                "isError": not result.success
            }
        }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id, 
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found"
            }
        }


@router.get("/")
async def mcp_server_info():
    """MCP server information endpoint."""
    return {
        "name": "kirishima-brain",
        "version": "1.0.0",
        "description": "Kirishima Brain MCP Server - AI Assistant Tools",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False
        },
        "endpoints": {
            "tools": "/mcp/tools",
            "execute": "/mcp/execute"
        }
    }


@router.get("/tools", response_model=MCPToolsResponse)
async def get_tools():
    """
    Return the list of available tools and their schemas for dynamic discovery.
    This allows agents to discover what tools are available at runtime.
    """
    tools = get_available_tools()
    return MCPToolsResponse(tools=tools)


@router.get("/copilot/tools", response_model=MCPToolsResponse)
async def get_copilot_tools():
    """
    Return the list of tools available to GitHub Copilot.
    Filtered subset of tools safe for external agent use.
    """
    tools = get_available_tools_for_client("copilot")
    return MCPToolsResponse(tools=tools)


@router.post("/memory", response_model=MCPToolResponse)
async def mcp_memory(request: MCPToolRequest):
    """
    MCP endpoint for comprehensive memory management.
    Supports search, create, update, delete, list, and get operations.
    """
    return await execute_tool_with_dependencies("memory", request.parameters)


@router.post("/github_issue", response_model=MCPToolResponse)
async def mcp_github_issue(request: MCPToolRequest):
    """
    MCP endpoint for GitHub issue management.
    """
    return await execute_tool_with_dependencies("github_issue", request.parameters)


@router.post("/manage_prompt", response_model=MCPToolResponse)
async def mcp_manage_prompt(request: MCPToolRequest):
    """
    MCP endpoint for agent's system prompt management.
    Internal use only - not available to external clients like Copilot.
    """
    return await execute_tool_with_dependencies("manage_prompt", request.parameters)


@router.post("/email", response_model=MCPToolResponse)
async def mcp_email(request: MCPToolRequest):
    """
    MCP endpoint for email operations.
    Supports draft, send, search, and list actions.
    """
    return await execute_tool_with_dependencies("email", request.parameters)


@router.post("/execute", response_model=MCPToolResponse)
async def execute_tool(request: MCPToolRequest):
    """
    Generic tool execution endpoint with dependency resolution.
    """
    if not is_tool_available(request.tool_name):
        raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")
    
    tool_registry = _load_tool_registry()
    return await execute_tool_with_dependencies(request.tool_name, request.parameters, tool_registry)


@router.get("/validate")
async def validate_dependencies():
    """Validate all tool dependencies."""
    return validate_all_dependencies()


@router.get("/execution_plan/{tool_name}")
async def get_execution_plan_endpoint(tool_name: str):
    """Get the execution plan for a specific tool."""
    try:
        from app.services.mcp.registry import ToolRegistry
        from app.services.mcp.dependencies import DependencyResolver
        
        registry = ToolRegistry()
        resolver = DependencyResolver(registry)
        execution_plan = resolver.get_execution_plan(tool_name)
        
        return {
            "tool_name": tool_name,
            "execution_plan": execution_plan,
            "dependencies_found": len(execution_plan) > 1
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
