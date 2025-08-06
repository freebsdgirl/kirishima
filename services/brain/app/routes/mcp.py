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


async def _handle_jsonrpc_request(request: dict, client_type: str = "internal") -> dict:
    """
    Consolidated JSON-RPC handler for MCP protocol requests.
    
    Args:
        request: The JSON-RPC request dict
        client_type: Client type for tool filtering ("internal", "copilot", "external")
    
    Returns:
        JSON-RPC response dict
    """
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    # Client-specific configuration
    client_configs = {
        "internal": {
            "server_name": "kirishima-brain",
            "get_tools": get_available_tools,
            "is_tool_available": is_tool_available,
            "error_suffix": ""
        },
        "copilot": {
            "server_name": "kirishima-brain-copilot", 
            "get_tools": lambda: get_available_tools_for_client("copilot"),
            "is_tool_available": lambda tool_name: is_tool_available_for_client(tool_name, "copilot"),
            "error_suffix": " or not authorized for Copilot"
        },
        "external": {
            "server_name": "kirishima-brain-external",
            "get_tools": lambda: get_available_tools_for_client("external"),
            "is_tool_available": lambda tool_name: is_tool_available_for_client(tool_name, "external"),
            "error_suffix": " or not authorized for external clients"
        }
    }
    
    config = client_configs.get(client_type, client_configs["internal"])
    
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
                    "name": config["server_name"],
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        tools = config["get_tools"]()
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
        
        if not config["is_tool_available"](tool_name):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found{config['error_suffix']}"
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


@router.post("/")
async def mcp_handler(request: dict):
    """
    Main MCP protocol handler for JSON-RPC requests.
    """
    return await _handle_jsonrpc_request(request, "internal")


@router.post("/copilot/")
async def mcp_copilot_handler(request: dict):
    """
    MCP protocol handler for GitHub Copilot with filtered tools.
    Same protocol as main MCP endpoint but with restricted tool access.
    """
    return await _handle_jsonrpc_request(request, "copilot")


@router.post("/external/")
async def mcp_external_handler(request: dict):
    """
    MCP protocol handler for external clients with filtered tools.
    Same protocol as main MCP endpoint but with restricted tool access.
    """
    return await _handle_jsonrpc_request(request, "external")


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


@router.get("/external/tools", response_model=MCPToolsResponse)
async def get_external_tools():
    """
    Return the list of tools available to external clients.
    Filtered subset of tools safe for external agent use.
    """
    tools = get_available_tools_for_client("external")
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


@router.post("/calendar", response_model=MCPToolResponse)
async def mcp_calendar(request: MCPToolRequest):
    """
    MCP endpoint for calendar operations.
    Supports create_event, search_events, get_upcoming, delete_event, and list_events actions.
    """
    return await execute_tool_with_dependencies("calendar", request.parameters)


@router.post("/contacts", response_model=MCPToolResponse)
async def mcp_contacts(request: MCPToolRequest):
    """
    MCP endpoint for contacts operations.
    Supports get_contact, list_contacts, search_contacts, create_contact, update_contact, and delete_contact actions.
    """
    return await execute_tool_with_dependencies("contacts", request.parameters)


@router.post("/stickynotes", response_model=MCPToolResponse)
async def mcp_stickynotes(request: MCPToolRequest):
    """
    MCP endpoint for stickynotes operations (default task list).
    Supports list, create, update, complete, and delete actions.
    """
    return await execute_tool_with_dependencies("stickynotes", request.parameters)


@router.post("/lists", response_model=MCPToolResponse)
async def mcp_lists(request: MCPToolRequest):
    """
    MCP endpoint for task list management operations.
    Supports list_task_lists, create_task_list, delete_task_list, list_tasks, create_task, and delete_task actions.
    """
    return await execute_tool_with_dependencies("lists", request.parameters)


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
