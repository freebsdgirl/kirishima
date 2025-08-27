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

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import importlib
from threading import Lock
from shared.models.mcp import ToolsListResponse, ToolCallRequest, ToolCallResponse, Tool, ToolAnnotation

import json

def get_all_tools():
    with open("/app/app/config/tools.json", "r") as f:
        data = json.load(f)
    tools = []
    for tool in data:
        if isinstance(tool.get("annotations"), dict):
            tool["annotations"] = ToolAnnotation(**tool["annotations"])
        tools.append(Tool(**tool))
    return tools

def get_copilot_tools():
    return [t for t in get_all_tools() if t.name in ("get_personality", "github_issue")]

router = APIRouter()


async def _handle_jsonrpc_request(request: dict, client_type: str = "internal") -> dict:
    """
    Minimal JSON-RPC handler for MCP protocol requests, using new models and registry.
    """
    logger.debug(f"_handle_jsonrpc_request input: {request}")
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    # Early exit for notifications (no id)
    if request_id is None:
        # JSON-RPC spec: notifications must not get a response
        logger.debug("Received notification (no id); returning no response.")
        return None

    # Tool filtering
    if client_type == "copilot":
        tools = get_copilot_tools()
    else:
        tools = get_all_tools()

    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kirishima-brain", "version": "1.0.0"}
            }
        }
        return response

    elif method == "tools/list":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": t.name,
                        "title": getattr(t, "title", t.name),
                        "description": t.description,
                        "inputSchema": t.inputSchema,
                        "outputSchema": t.outputSchema,
                        "annotations": t.annotations,
                        "_meta": None
                    } for t in tools
                ]
            }
        }
        return response

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        allowed = [t.name for t in tools]
        if tool_name not in allowed:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found or not allowed"}
            }
        # Dynamically import and call the tool implementation
        try:
            module = importlib.import_module(f"app.services.mcp.{tool_name}")
            tool_func = getattr(module, tool_name)
            result = await tool_func(arguments)
            # If result is a ToolCallResponse, extract the actual result content
            if hasattr(result, "model_dump"):
                result_dict = result.model_dump()
                # Extract the actual result, not the wrapper
                actual_result = result_dict.get("result")
                if result_dict.get("error"):
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": result_dict["error"]}
                    }
            else:
                actual_result = result
            
            # Return structured content - MCP library requires structuredContent to be a dict
            if isinstance(actual_result, list):
                structured_content = {"items": actual_result}
            elif isinstance(actual_result, dict):
                structured_content = actual_result  
            else:
                structured_content = {"value": actual_result}
                
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool {tool_name} executed successfully"}],
                    "structuredContent": structured_content,
                    "isError": False
                }
            }
        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": f"Tool execution failed: {str(e)}"}
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"}
        }


@router.post("/")
async def mcp_handler(request: dict):
    """
    Main MCP protocol handler for JSON-RPC requests.
    """
    logger.debug(f"/mcp/: {request}")
    return await _handle_jsonrpc_request(request, "internal")


@router.post("/copilot/")
@router.post("/copilot")
async def mcp_copilot_handler(request: dict):
    """
    MCP protocol handler for GitHub Copilot with filtered tools.
    Same protocol as main MCP endpoint but with restricted tool access.
    """
    logger.debug(f"/mcp/copilot/: {request}")
    return await _handle_jsonrpc_request(request, "copilot")


@router.post("/external/")
@router.post("/external")
async def mcp_external_handler(request: dict):
    """
    MCP protocol handler for external clients with filtered tools.
    Same protocol as main MCP endpoint but with restricted tool access.
    """
    logger.debug(f"/mcp/external/: {request}")
    return await _handle_jsonrpc_request(request, "external")


@router.get("/")
async def mcp_server_info():
    """MCP server information endpoint."""
    logger.debug("/mcp/ GET")
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


@router.get("/tools", response_model=ToolsListResponse)
async def get_tools():
    """
    Return the list of available tools and their schemas for dynamic discovery.
    """
    tools = get_all_tools()
    return ToolsListResponse(tools=tools)


@router.get("/copilot/tools", response_model=ToolsListResponse)
async def get_copilot_tools_endpoint():
    """
    Return the list of tools available to GitHub Copilot.
    Only get_personality and github_issue are exposed.
    """
    tools = get_copilot_tools()
    return ToolsListResponse(tools=tools)


@router.post("/execute", response_model=ToolCallResponse)
async def execute_tool(request: ToolCallRequest):
    """
    Generic tool execution endpoint.
    """
    if request.name not in [t.name for t in get_all_tools()]:
        return ToolCallResponse(result=None, error=f"Tool '{request.name}' not found")
    return ToolCallResponse(result={"status": "success", "tool": request.name, "args": request.arguments})


@router.post("/copilot/execute", response_model=ToolCallResponse)
async def execute_copilot_tool(request: ToolCallRequest):
    """
    Copilot tool execution endpoint.
    Only get_personality and github_issue are allowed.
    """
    if request.name not in ("get_personality", "github_issue"):
        return ToolCallResponse(result=None, error="Copilot is only allowed to call get_personality and github_issue tools.")
    
    # Actually execute the tool using dynamic import
    try:
        module = importlib.import_module(f"app.services.mcp.{request.name}")
        tool_func = getattr(module, request.name)
        return await tool_func(request.arguments)
    except Exception as e:
        logger.error(f"Error executing tool {request.name}: {e}")
        return ToolCallResponse(result=None, error=f"Tool execution failed: {str(e)}")


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
