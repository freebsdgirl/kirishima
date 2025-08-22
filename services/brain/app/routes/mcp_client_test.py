# Temporary test route for MCP client
from fastapi import APIRouter, Query
from typing import Optional
import asyncio
from app.services.mcp_client.client import MCPClient
from app.services.mcp_client.util import mcp_tools_to_openai

router = APIRouter()

@router.get("/mcp_client/test/list_tools")
async def list_tools(url: Optional[str] = Query(default="http://brain:4207/mcp/")):
    client = MCPClient(url)
    tools = await client.list_tools()
    return {"tools": tools}

@router.post("/mcp_client/test/call_tool")
async def call_tool(
    url: Optional[str] = Query(default="http://brain:4207/mcp/"),
    tool_name: str = Query(...),
    arguments: Optional[dict] = None
):
    client = MCPClient(url)
    result = await client.call_tool(tool_name, arguments or {})
    return {"result": result}


@router.get("/mcp_client/test/tools_json")
async def tools_json(url: Optional[str] = Query(default="http://brain:4207/mcp/")):
    client = MCPClient(url)
    tools = await client.list_tools()
    openai_tools = mcp_tools_to_openai(tools)
    return {"tools": openai_tools}
