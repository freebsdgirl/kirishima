"""
MCP (Model Context Protocol) routes for exposing Brain's tools as standardized API endpoints.

This module implements the MCP server functionality, allowing external agents (like Copilot)
to discover and call Brain's tools in a standardized way.

All tool discovery and execution is backed by the decorator-based registry in app.tools.
No JSON tool definition files, no dynamic importlib loading.

Key endpoints:
- POST /mcp/ — JSON-RPC handler (internal clients)
- POST /mcp/copilot/ — JSON-RPC handler (Copilot, filtered tools)
- POST /mcp/external/ — JSON-RPC handler (external clients, filtered tools)
- GET /mcp/ — Server info
- GET /mcp/tools — Tool discovery (OpenAI format)
- POST /mcp/execute — Tool execution
"""

from fastapi import APIRouter

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.tools import get_mcp_tools, get_openai_tools, call_tool

router = APIRouter()


async def _handle_jsonrpc_request(request: dict, client_type: str = "internal") -> dict:
    """
    JSON-RPC handler for MCP protocol requests.
    Tool discovery and execution backed entirely by app.tools registry.
    """
    logger.debug(f"_handle_jsonrpc_request input: {request}")
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    # Early exit for notifications (no id)
    if request_id is None:
        logger.debug("Received notification (no id); returning no response.")
        return None

    # Get tools from the new registry, filtered by client type
    tools = get_mcp_tools(client_type)

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kirishima-brain", "version": "1.0.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": t["name"],
                        "title": t["name"],
                        "description": t["description"],
                        "inputSchema": t["inputSchema"],
                        "_meta": None,
                    } for t in tools
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        allowed_names = [t["name"] for t in tools]
        if tool_name not in allowed_names:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found or not allowed for client '{client_type}'"}
            }

        # Execute via the unified registry — no importlib, no HTTP self-call
        result = await call_tool(tool_name, arguments)

        # Tool-level errors are returned as successful MCP responses with
        # isError=True. Do NOT convert them to JSON-RPC protocol errors —
        # that causes McpError on the client side and prevents agents from
        # seeing the actual error message.
        if result.error:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result.error}],
                    "structuredContent": {"success": False, "error": result.error},
                    "isError": True,
                }
            }

        actual_result = result.result

        # Normalize structuredContent to dict (MCP spec requirement)
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
                "isError": False,
            }
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


@router.get("/tools")
async def get_tools():
    """Return all registered tools in OpenAI format for dynamic discovery."""
    return {"tools": get_openai_tools("internal")}


@router.get("/copilot/tools")
async def get_copilot_tools_endpoint():
    """Return tools available to GitHub Copilot."""
    return {"tools": get_openai_tools("copilot")}


@router.post("/execute")
async def execute_tool_endpoint(request: dict):
    """Generic tool execution endpoint."""
    name = request.get("name")
    arguments = request.get("arguments", {})
    if not name:
        return {"result": None, "error": "Missing 'name' in request"}
    result = await call_tool(name, arguments)
    return result.model_dump()


@router.post("/copilot/execute")
async def execute_copilot_tool(request: dict):
    """Copilot tool execution endpoint with access control."""
    name = request.get("name")
    arguments = request.get("arguments", {})
    if not name:
        return {"result": None, "error": "Missing 'name' in request"}
    # Verify copilot access
    allowed = [t["function"]["name"] for t in get_openai_tools("copilot")]
    if name not in allowed:
        return {"result": None, "error": f"Tool '{name}' not allowed for copilot client"}
    result = await call_tool(name, arguments)
    return result.model_dump()
