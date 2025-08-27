"""Tool registry and discovery service for MCP.

Adds robust path resolution for configuration so that running the brain service
directly (outside Docker) still loads `mcp_clients.json` instead of silently
falling back to permissive defaults (root cause of missing filtering).
"""

from shared.models.mcp import MCPToolSchema
from typing import Dict, Any, List
import json
from pathlib import Path

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


def _resolve_config_file(filename: str) -> Path | None:
    """Locate a config file by checking several candidate paths.

    Order:
      1. Relative to this file: ../config/<filename>
      2. /app/app/config/<filename> (Docker layout)
      3. /app/config/<filename> (alternate layout)
    Returns first existing path or None.
    """
    module_dir = Path(__file__).resolve().parent
    candidates = [
        (module_dir.parent / 'config' / filename).resolve(),
        Path('/app/app/config') / filename,
        Path('/app/config') / filename,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_json_file(filename: str, default: Dict[str, Any]) -> Dict[str, Any]:
    path = _resolve_config_file(filename)
    if not path:
        logger.warning(
            "MCP config file '%s' not found in any candidate path; using default", filename
        )
        return default
    try:
        with path.open('r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error("Failed to load MCP config '%s': %s; using default", path, e)
        return default


def _load_tool_registry() -> Dict[str, Any]:
    return _load_json_file('mcp_tools.json', {})


def _load_client_registry() -> Dict[str, Any]:
    return _load_json_file('mcp_clients.json', {
        "internal": {"allowed_tools": ["*"], "restricted_tools": []}
    })


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
    logger.debug(
        "MCP tool filter load client_type=%s allowed=%s restricted=%s", 
        client_type, allowed_tools, restricted_tools
    )
    
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
    logger.debug(
        "MCP tool availability check client_type=%s tool=%s allowed_list=%s restricted_list=%s", 
        client_type, tool_name, allowed_tools, restricted_tools
    )
    
    # First check if tool exists
    if tool_name not in TOOL_REGISTRY:
        return False
    
    # Check permissions
    if "*" in allowed_tools:
        return tool_name not in restricted_tools
    else:
        return tool_name in allowed_tools and tool_name not in restricted_tools
