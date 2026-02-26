"""Kirishima tool registry — auto-discovery + unified dispatch.

On import, this module scans all .py files in the tools/ directory, imports
each one, and finds functions decorated with @tool (identified by _tool_meta
attribute). Old tool files without @tool decorators are silently ignored.

Public API:
    get_tool(name)                          -> callable or None
    get_openai_tools(client_type)           -> list of OpenAI function-calling dicts
    get_mcp_tools(client_type)              -> list of MCP tool dicts
    get_always_tools(client_type)           -> OpenAI format, always=True tools only
    get_routed_tools_catalog()              -> {name: description} for router
    get_openai_tools_by_names(names, ct)    -> OpenAI format for specific tool names
    call_tool(name, params)                 -> ToolResponse (local or MCPClient fallback)
"""

import importlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")

# ---------------------------------------------------------------------------
# Internal registry: populated by _discover_tools() at module load time
# ---------------------------------------------------------------------------
_REGISTRY: Dict[str, Dict[str, Any]] = {}
# {tool_name: {"function": async_callable, "meta": ToolMeta}}

# Files that are part of the infrastructure, not tool modules
_EXCLUDED_FILES = {"__init__", "base", "router"}


def _discover_tools() -> None:
    """Scan this package's directory for @tool-decorated functions."""
    package_dir = Path(__file__).resolve().parent

    for py_file in sorted(package_dir.glob("*.py")):
        module_stem = py_file.stem
        if module_stem in _EXCLUDED_FILES or module_stem.startswith("_"):
            continue

        try:
            module = importlib.import_module(f".{module_stem}", package=__package__)
        except Exception:
            logger.debug("Skipping %s — import failed (likely legacy tool)", module_stem)
            continue

        # Walk module attributes looking for _tool_meta
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            meta = getattr(obj, "_tool_meta", None)
            if meta is not None:
                if meta.name in _REGISTRY:
                    logger.warning(
                        "Duplicate tool name '%s' in %s — overwriting previous registration",
                        meta.name, module_stem,
                    )
                _REGISTRY[meta.name] = {"function": obj, "meta": meta}
                logger.info("Registered tool: %s (always=%s, persistent=%s)", meta.name, meta.always, meta.persistent)


# ---------------------------------------------------------------------------
# Client access control (reads mcp_clients.json)
# ---------------------------------------------------------------------------
def _resolve_config_file(filename: str) -> Optional[Path]:
    """Locate a config file by checking several candidate paths."""
    module_dir = Path(__file__).resolve().parent
    candidates = [
        (module_dir.parent / "config" / filename).resolve(),
        Path("/app/app/config") / filename,
        Path("/app/config") / filename,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_client_registry() -> Dict[str, Any]:
    path = _resolve_config_file("mcp_clients.json")
    if not path:
        logger.warning("mcp_clients.json not found; defaulting to allow-all for 'internal'")
        return {"internal": {"allowed_tools": ["*"], "restricted_tools": []}}
    try:
        with path.open("r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load mcp_clients.json: %s; defaulting", e)
        return {"internal": {"allowed_tools": ["*"], "restricted_tools": []}}


def _is_tool_allowed(tool_name: str, client_type: str) -> bool:
    """Check if a tool is allowed for a given client type."""
    client_registry = _load_client_registry()
    client_config = client_registry.get(client_type, client_registry.get("internal", {}))
    allowed = client_config.get("allowed_tools", [])
    restricted = client_config.get("restricted_tools", [])

    if "*" in allowed:
        return tool_name not in restricted
    return tool_name in allowed and tool_name not in restricted


# ---------------------------------------------------------------------------
# Format converters
# ---------------------------------------------------------------------------
def _to_openai_format(meta) -> dict:
    """Convert ToolMeta to OpenAI function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": meta.name,
            "description": meta.description,
            "parameters": meta.parameters,
        },
    }


def _to_mcp_format(meta) -> dict:
    """Convert ToolMeta to MCP tool list format."""
    return {
        "name": meta.name,
        "description": meta.description,
        "inputSchema": meta.parameters,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_tool(name: str):
    """Return the callable for a registered tool, or None."""
    entry = _REGISTRY.get(name)
    return entry["function"] if entry else None


def get_tool_meta(name: str):
    """Return the ToolMeta for a registered tool, or None."""
    entry = _REGISTRY.get(name)
    return entry["meta"] if entry else None


def get_openai_tools(client_type: str = "internal") -> List[dict]:
    """Return all registered tools in OpenAI function-calling format, filtered by client access."""
    return [
        _to_openai_format(entry["meta"])
        for entry in _REGISTRY.values()
        if _is_tool_allowed(entry["meta"].name, client_type)
    ]


def get_mcp_tools(client_type: str = "internal") -> List[dict]:
    """Return all registered tools in MCP format, filtered by client access."""
    return [
        _to_mcp_format(entry["meta"])
        for entry in _REGISTRY.values()
        if _is_tool_allowed(entry["meta"].name, client_type)
    ]


def get_always_tools(client_type: str = "internal") -> List[dict]:
    """Return always=True tools in OpenAI format, filtered by client access."""
    return [
        _to_openai_format(entry["meta"])
        for entry in _REGISTRY.values()
        if entry["meta"].always and _is_tool_allowed(entry["meta"].name, client_type)
    ]


def get_routed_tools_catalog() -> Dict[str, str]:
    """Return {name: description} for all always=False tools (for the tool router)."""
    return {
        entry["meta"].name: entry["meta"].description
        for entry in _REGISTRY.values()
        if not entry["meta"].always
    }


def get_openai_tools_by_names(names: List[str], client_type: str = "internal") -> List[dict]:
    """Return OpenAI format tools for specific tool names, filtered by client access."""
    result = []
    for name in names:
        entry = _REGISTRY.get(name)
        if entry and _is_tool_allowed(name, client_type):
            result.append(_to_openai_format(entry["meta"]))
    return result


def get_guidance_for_tools(tool_names: List[str]) -> str:
    """Return concatenated guidance strings for tools that have them."""
    parts = []
    for name in tool_names:
        entry = _REGISTRY.get(name)
        if entry and entry["meta"].guidance:
            parts.append(f"[{name}] {entry['meta'].guidance}")
    return "\n".join(parts)


async def call_tool(name: str, params: dict):
    """Execute a tool by name. Falls through to external MCPClient if not found locally.

    Returns a ToolResponse on success/failure. If the tool is external (MCPClient),
    the raw result is wrapped in a ToolResponse.
    """
    from app.tools.base import ToolResponse

    # Try local registry first
    entry = _REGISTRY.get(name)
    if entry:
        try:
            result = await entry["function"](params)
            if isinstance(result, ToolResponse):
                return result
            # Defensive: wrap non-ToolResponse returns
            return ToolResponse(result=result)
        except Exception as e:
            logger.error("Tool '%s' raised: %s", name, e, exc_info=True)
            return ToolResponse(error=str(e))

    # Fallthrough: try external MCP servers
    try:
        from app.services.mcp_client.client import MCPClient

        mcp_clients = MCPClient.from_config()
        for mcp_client in mcp_clients:
            try:
                tools = await mcp_client.list_tools()
                if any(t.get("name") == name for t in tools):
                    raw_result = await mcp_client.call_tool(name, params)
                    return ToolResponse(result=raw_result)
            except Exception as e:
                logger.debug("MCPClient %s failed for tool '%s': %s", mcp_client.url, name, e)
                continue
    except Exception as e:
        logger.error("Failed to load MCPClient for fallthrough: %s", e)

    return ToolResponse(error=f"Tool '{name}' not found in local registry or external MCP servers")


def get_all_registered_names() -> List[str]:
    """Return all registered tool names."""
    return list(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Run auto-discovery on import
# ---------------------------------------------------------------------------
_discover_tools()
logger.info("Tool registry loaded: %d tools registered %s", len(_REGISTRY), list(_REGISTRY.keys()))
