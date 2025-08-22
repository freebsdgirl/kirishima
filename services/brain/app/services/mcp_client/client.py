"""
Minimal MCP client for brain service.
- Reads MCP server config from .kirishima/config.json (supports multiple MCP servers)
- Provides list_tools and call_tool methods
"""
import os
import json
from typing import Any, Dict, List, Optional
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

class MCPClient:
    def __init__(self, url: str, short_name: Optional[str] = None, description: Optional[str] = None):
        self.url = url
        self.short_name = short_name
        self.description = description

    @staticmethod
    def get_all_servers(config_path: str = '/app/config/config.json') -> List[Dict[str, Any]]:
        """
        Return all MCP server entries from config.json (as a list of dicts)
        """
        with open(config_path) as f:
            config = json.load(f)
        return config.get('mcp', [])

    @staticmethod
    def from_config(config_path: str = '/app/config/config.json') -> List['MCPClient']:
        """
        Return a list of MCPClient instances for each MCP server in config.json
        """
        servers = MCPClient.get_all_servers(config_path)
        return [MCPClient(s.get('url'), s.get('short_name'), s.get('description')) for s in servers]

    async def list_tools(self) -> List[Dict[str, Any]]:
        async with streamablehttp_client(self.url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
                return [tool.dict() for tool in response.tools]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        async with streamablehttp_client(self.url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.structuredContent or result.content
