"""
This consolidates all the memory-related tools into a single tool with multiple actions.
All memory operations now go through the ledger service directly.
"""

import httpx
import os
from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")


async def memory_search_tool(keywords=None, category=None, topic_id=None, memory_id=None, min_keywords=2, created_after=None, created_before=None):
    """Search for memories via the ledger service."""
    try:
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

        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f'http://ledger:{ledger_port}/memories/_search',
                params=search_params
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise


async def add_memory_tool(memory, keywords=None, category=None, topic_id=None):
    """Add a memory via the ledger service."""
    try:
        memory_data = {
            "memory": memory,
            "keywords": keywords or [],
            "category": category,
            "topic_id": topic_id
        }
        
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f'http://ledger:{ledger_port}/memories',
                json=memory_data
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error adding memory: {e}")
        raise


async def delete_memory_tool(memory_id):
    """Delete a memory via the ledger service."""
    try:
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.delete(
                f'http://ledger:{ledger_port}/memories/by-id/{memory_id}'
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        raise


async def list_memory_tool(limit=10, offset=0):
    """List memories via the ledger service."""
    try:
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f'http://ledger:{ledger_port}/memories',
                params={"limit": limit, "offset": offset}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error listing memories: {e}")
        raise


async def memory(action: str, **kwargs):
    """
    Consolidated memory tool that routes to specific actions based on the action parameter.
    All operations are now delegated to the ledger service.
    
    :param action: The action to perform (e.g., 'search', 'add', 'delete', 'list').
    :param kwargs: Additional parameters required for the specific action.
    :return: Result of the specified memory action.
    """
    if action == "search":
        return await memory_search_tool(**kwargs)
    elif action == "add":
        return await add_memory_tool(**kwargs)
    elif action == "delete":
        memory_id = kwargs.get("memory_id")
        if not memory_id:
            raise ValueError("memory_id is required for delete action")
        return await delete_memory_tool(memory_id)
    elif action == "list":
        return await list_memory_tool(**kwargs)
    else:
        raise ValueError(f"Unknown action: {action}")
