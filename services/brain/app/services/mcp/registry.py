"""
Tool registry and discovery service for MCP.
"""

from shared.models.mcp import MCPToolSchema
from typing import Dict, Any, List
import json


def _load_tool_registry() -> Dict[str, Any]:
    """Load tool registry from JSON configuration file."""
    try:
        with open('/app/app/config/mcp_tools.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to empty registry if file doesn't exist
        return {}


def _load_client_registry() -> Dict[str, Any]:
    """Load client configuration from JSON file."""
    try:
        with open('/app/config/mcp_clients.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to default internal-only access
        return {
            "internal": {
                "allowed_tools": ["*"],
                "restricted_tools": []
            }
        }


# Tool registry - loaded from JSON configuration
TOOL_REGISTRY = _load_tool_registry()


class ToolRegistry:
    """Tool registry class for dependency resolution."""
    
    def __init__(self):
        """Initialize with the global tool registry."""
        self.registry = TOOL_REGISTRY
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Return available tools as raw dict data."""
        return list(self.registry.values())
    
    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available in the registry."""
        return tool_name in self.registry
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """Get tool information from the registry."""
        return self.registry.get(tool_name)


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


def get_available_tools_for_client(client_type: str = "internal") -> List[MCPToolSchema]:
    """
    Return the list of available tools filtered by client type.
    
    Args:
        client_type: The client type (internal, copilot, external)
    """
    client_registry = _load_client_registry()
    client_config = client_registry.get(client_type, client_registry.get("internal"))
    
    allowed_tools = client_config.get("allowed_tools", [])
    restricted_tools = client_config.get("restricted_tools", [])
    
    tools = []
    for tool_name, tool_info in TOOL_REGISTRY.items():
        # Check if tool is allowed
        tool_allowed = False
        
        if "*" in allowed_tools:
            # Full access - check if tool is specifically restricted
            tool_allowed = tool_name not in restricted_tools
        else:
            # Limited access - check if tool is specifically allowed
            tool_allowed = tool_name in allowed_tools and tool_name not in restricted_tools
        
        if tool_allowed:
            tools.append(MCPToolSchema(
                name=tool_name,
                description=tool_info["description"],
                parameters=tool_info["parameters"],
                returns=tool_info["returns"]
            ))
    
    return tools


def is_tool_available_for_client(tool_name: str, client_type: str = "internal") -> bool:
    """Check if a tool is available for the specified client type."""
    client_registry = _load_client_registry()
    client_config = client_registry.get(client_type, client_registry.get("internal"))
    
    allowed_tools = client_config.get("allowed_tools", [])
    restricted_tools = client_config.get("restricted_tools", [])
    
    # First check if tool exists
    if tool_name not in TOOL_REGISTRY:
        return False
    
    # Check permissions
    if "*" in allowed_tools:
        return tool_name not in restricted_tools
    else:
        return tool_name in allowed_tools and tool_name not in restricted_tools
