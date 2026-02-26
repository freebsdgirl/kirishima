"""memory tool — comprehensive memory management via the ledger service.

Actions: search, create, update, delete, list, get.

Also exports memory_search_tool() for direct use by brainlets.
"""

import os
from typing import Any, Dict

import httpx

from app.tools.base import tool, ToolResponse
from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")

_LEDGER_PORT = os.getenv("LEDGER_PORT", "4203")
_LEDGER_BASE = f"http://ledger:{_LEDGER_PORT}"
_TIMEOUT = 60


@tool(
    name="memory",
    description="Comprehensive memory management - search, create, update, delete, list memories",
    persistent=True,
    always=True,
    clients=["internal", "external"],
    service="ledger",
    guidance="Always search before creating to avoid duplicates. Use specific keywords for better results.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "create", "update", "delete", "list", "get"],
                "description": "The action to perform: search, create, update, delete, list, or get",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keywords to search for (search action)",
            },
            "category": {
                "type": "string",
                "description": "Category filter for search or category for new memory",
            },
            "topic_id": {
                "type": "string",
                "description": "Topic ID filter for search or topic assignment",
            },
            "memory_id": {
                "type": "string",
                "description": "Memory ID for get, update, or delete actions",
            },
            "memory": {
                "type": "string",
                "description": "Memory text content for create or update actions",
            },
            "min_keywords": {
                "type": "integer",
                "description": "Minimum matching keywords for search (default: 2)",
                "default": 2,
            },
            "created_after": {
                "type": "string",
                "description": "ISO timestamp - return memories created after this time",
            },
            "created_before": {
                "type": "string",
                "description": "ISO timestamp - return memories created before this time",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results for list/search (default: 10)",
                "default": 10,
            },
            "offset": {
                "type": "integer",
                "description": "Offset for pagination in list action (default: 0)",
                "default": 0,
            },
        },
        "required": ["action"],
    },
)
async def memory_tool(parameters: dict) -> ToolResponse:
    """Dispatch to the appropriate memory action."""
    action = parameters.get("action", "search")

    try:
        if action == "search":
            return await _search(parameters)
        elif action == "create":
            return await _create(parameters)
        elif action == "update":
            return await _update(parameters)
        elif action == "delete":
            return await _delete(parameters)
        elif action == "list":
            return await _list(parameters)
        elif action == "get":
            return await _get(parameters)
        else:
            return ToolResponse(error=f"Unknown action: {action}")
    except Exception as e:
        logger.error("memory tool error: %s", e, exc_info=True)
        return ToolResponse(error=str(e))


# ---------------------------------------------------------------------------
# Action handlers — all return ToolResponse consistently
# ---------------------------------------------------------------------------

async def _search(params: dict) -> ToolResponse:
    search_params: Dict[str, Any] = {}

    keywords = params.get("keywords")
    if keywords is not None:
        search_params["keywords"] = keywords if isinstance(keywords, list) else [keywords]

    for key in ("category", "topic_id", "memory_id", "created_after", "created_before"):
        val = params.get(key)
        if val is not None:
            search_params[key] = val

    min_kw = params.get("min_keywords", 2)
    if min_kw is not None:
        search_params["min_keywords"] = int(min_kw)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_LEDGER_BASE}/memories/_search", params=search_params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        return ToolResponse(error=f"Ledger HTTP error: {e}")

    # Compact format for token efficiency: id|timestamp|memory_text
    memories = data.get("memories", [])
    if memories:
        compact = [f"{m['id']}|{m['created_at']}|{m['memory']}" for m in memories]
        return ToolResponse(result={"status": "ok", "memories": compact, "count": len(compact)})

    return ToolResponse(result=data)


async def _create(params: dict) -> ToolResponse:
    memory_text = params.get("memory")
    if not memory_text:
        return ToolResponse(error="memory text is required for create action")

    body = {
        "memory": memory_text,
        "keywords": params.get("keywords", []),
        "category": params.get("category"),
        "topic_id": params.get("topic_id"),
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{_LEDGER_BASE}/memories", json=body)
            resp.raise_for_status()
            return ToolResponse(result=resp.json())
    except httpx.HTTPError as e:
        return ToolResponse(error=f"Ledger HTTP error: {e}")


async def _update(params: dict) -> ToolResponse:
    memory_id = params.get("memory_id")
    if not memory_id:
        return ToolResponse(error="memory_id is required for update action")

    update_data: Dict[str, Any] = {}
    for key in ("memory", "keywords", "category", "topic_id"):
        if key in params:
            update_data[key] = params[key]

    if not update_data:
        return ToolResponse(error="At least one field to update is required")

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.patch(f"{_LEDGER_BASE}/memories/by-id/{memory_id}", json=update_data)
            resp.raise_for_status()
            return ToolResponse(result=resp.json())
    except httpx.HTTPError as e:
        return ToolResponse(error=f"Ledger HTTP error: {e}")


async def _delete(params: dict) -> ToolResponse:
    memory_id = params.get("memory_id")
    if not memory_id:
        return ToolResponse(error="memory_id is required for delete action")

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(f"{_LEDGER_BASE}/memories/by-id/{memory_id}")
            resp.raise_for_status()
            return ToolResponse(result=resp.json())
    except httpx.HTTPError as e:
        return ToolResponse(error=f"Ledger HTTP error: {e}")


async def _list(params: dict) -> ToolResponse:
    limit = params.get("limit", 10)
    offset = params.get("offset", 0)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_LEDGER_BASE}/memories",
                params={"limit": limit, "offset": offset},
            )
            resp.raise_for_status()
            return ToolResponse(result=resp.json())
    except httpx.HTTPError as e:
        return ToolResponse(error=f"Ledger HTTP error: {e}")


async def _get(params: dict) -> ToolResponse:
    memory_id = params.get("memory_id")
    if not memory_id:
        return ToolResponse(error="memory_id is required for get action")

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_LEDGER_BASE}/memories/by-id/{memory_id}")
            resp.raise_for_status()
            return ToolResponse(result=resp.json())
    except httpx.HTTPError as e:
        return ToolResponse(error=f"Ledger HTTP error: {e}")


# ---------------------------------------------------------------------------
# Standalone helper — used by brainlets/memory_search.py directly
# ---------------------------------------------------------------------------

async def memory_search_tool(
    keywords=None,
    category=None,
    topic_id=None,
    memory_id=None,
    min_keywords=2,
    created_after=None,
    created_before=None,
):
    """Search memories via ledger. Returns raw JSON (not ToolResponse).

    This is a convenience wrapper for brainlets that need direct search access
    without going through the @tool decorator dispatch.
    """
    search_params = {}
    if keywords is not None:
        search_params["keywords"] = keywords if isinstance(keywords, list) else [keywords]
    if category is not None:
        search_params["category"] = category
    if topic_id is not None:
        search_params["topic_id"] = topic_id
    if memory_id is not None:
        search_params["memory_id"] = memory_id
    if min_keywords is not None:
        search_params["min_keywords"] = int(min_keywords)
    if created_after is not None:
        search_params["created_after"] = created_after
    if created_before is not None:
        search_params["created_before"] = created_before

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_LEDGER_BASE}/memories/_search", params=search_params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Error searching memories: %s", e)
        raise
