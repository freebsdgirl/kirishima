"""
Tool registry and discovery service for MCP.
"""

from shared.models.mcp import MCPToolSchema
from typing import Dict, Any, List
import json


def _load_tool_registry() -> Dict[str, Any]:
    """Load tool registry from JSON configuration file."""
    try:
        with open('/app/config/mcp_tools.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to empty registry if file doesn't exist
        return {}


# Tool registry - loaded from JSON configuration
TOOL_REGISTRY = _load_tool_registry()


def get_available_tools() -> List[MCPToolSchema]:
    """
    Return the list of available tools and their schemas for dynamic discovery.
    """
    tools = []
    for tool_name, tool_info in TOOL_REGISTRY.items():
        tools.append(MCPToolSchema(
            name=tool_name,
            description=tool_info["description"],
            parameters=tool_info["parameters"],
            returns=tool_info["returns"]
        ))
    
    return tools


def is_tool_available(tool_name: str) -> bool:
    """Check if a tool is available in the registry."""
    return tool_name in TOOL_REGISTRY


def get_tool_info(tool_name: str) -> Dict[str, Any]:
    """Get tool information from the registry."""
    return TOOL_REGISTRY.get(tool_name)
