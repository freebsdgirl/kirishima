"""
This module provides comprehensive memory management functionality via the MCP (Memory Control Protocol) service.
It supports the following operations on memory entries:
- search: Search for memories using various filters such as keywords, category, topic_id, memory_id, creation date, etc.
- create: Create a new memory entry with optional keywords, category, and topic association.
- update: Update an existing memory entry by its ID, allowing changes to memory text, keywords, category, or topic.
- delete: Delete a memory entry by its ID.
- list: List memory entries with pagination support (limit and offset).
- get: Retrieve a specific memory entry by its ID.
Each operation communicates asynchronously with the ledger service using HTTP requests, and returns a standardized
MCPToolResponse indicating success or failure, along with the result or error message.
Logging is provided for error handling and debugging purposes.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any
import httpx
import os

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


async def memory(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Comprehensive memory management via MCP.
    Supports search, create, update, delete, and list operations.
    
    Actions:
    - search: Search memories with filters (keywords, category, topic_id, etc.)
    - create: Create a new memory entry
    - update: Update an existing memory
    - delete: Delete a memory by ID
    - list: List memories with pagination
    - get: Get a specific memory by ID
    """
    try:
        action = parameters.get("action", "search")
        
        if action == "search":
            return await _memory_search(parameters)
        elif action == "create":
            return await _memory_create(parameters)
        elif action == "update":
            return await _memory_update(parameters)
        elif action == "delete":
            return await _memory_delete(parameters)
        elif action == "list":
            return await _memory_list(parameters)
        elif action == "get":
            return await _memory_get(parameters)
        else:
            return MCPToolResponse(success=False, error=f"Unknown action: {action}")
    
    except Exception as e:
        logger.error(f"Memory tool error: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _memory_search(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Search for memories via the ledger service."""
    try:
        search_params = {}
        
        # Build search parameters
        keywords = parameters.get("keywords")
        if keywords is not None:
            search_params["keywords"] = keywords if isinstance(keywords, list) else [keywords]
        
        category = parameters.get("category")
        if category is not None:
            search_params["category"] = category
            
        topic_id = parameters.get("topic_id")
        if topic_id is not None:
            search_params["topic_id"] = topic_id
            
        memory_id = parameters.get("memory_id")
        if memory_id is not None:
            search_params["memory_id"] = memory_id
            
        min_keywords = parameters.get("min_keywords", 2)
        if min_keywords is not None:
            search_params["min_keywords"] = int(min_keywords)
            
        created_after = parameters.get("created_after")
        if created_after is not None:
            search_params["created_after"] = created_after
            
        created_before = parameters.get("created_before")
        if created_before is not None:
            search_params["created_before"] = created_before

        # Call ledger service
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f'http://ledger:{ledger_port}/memories/_search',
                params=search_params
            )
            response.raise_for_status()
            result = response.json()
            
        # Convert to compact plaintext format: id|timestamp|memory
        if result.get("status") == "ok" and result.get("memories"):
            compact_memories = []
            for mem in result["memories"]:
                memory_line = f"{mem['id']}|{mem['created_at']}|{mem['memory']}"
                compact_memories.append(memory_line)
            
            compact_result = {
                "status": result["status"],
                "memories": compact_memories,
                "count": len(compact_memories)
            }
            return MCPToolResponse(success=True, result=compact_result)
        else:
            # Return original result if no memories or error status
            return MCPToolResponse(success=True, result=result)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in memory search: {e}")
        return MCPToolResponse(success=False, error=f"HTTP error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in memory search: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _memory_create(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Create a new memory via the ledger service."""
    try:
        memory_text = parameters.get("memory")
        if not memory_text:
            return MCPToolResponse(success=False, error="Memory text is required")
        
        memory_data = {
            "memory": memory_text,
            "keywords": parameters.get("keywords", []),
            "category": parameters.get("category"),
            "topic_id": parameters.get("topic_id")
        }
        
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f'http://ledger:{ledger_port}/memories',
                json=memory_data
            )
            response.raise_for_status()
            result = response.json()
            
        return MCPToolResponse(success=True, result=result)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in memory create: {e}")
        return MCPToolResponse(success=False, error=f"HTTP error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in memory create: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _memory_update(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Update an existing memory via the ledger service."""
    try:
        memory_id = parameters.get("memory_id")
        if not memory_id:
            return MCPToolResponse(success=False, error="Memory ID is required")
        
        update_data = {}
        if "memory" in parameters:
            update_data["memory"] = parameters["memory"]
        if "keywords" in parameters:
            update_data["keywords"] = parameters["keywords"]
        if "category" in parameters:
            update_data["category"] = parameters["category"]
        if "topic_id" in parameters:
            update_data["topic_id"] = parameters["topic_id"]
            
        if not update_data:
            return MCPToolResponse(success=False, error="At least one field to update is required")
        
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.patch(
                f'http://ledger:{ledger_port}/memories/by-id/{memory_id}',
                json=update_data
            )
            response.raise_for_status()
            result = response.json()
            
        return MCPToolResponse(success=True, result=result)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in memory update: {e}")
        return MCPToolResponse(success=False, error=f"HTTP error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in memory update: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _memory_delete(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Delete a memory via the ledger service."""
    try:
        memory_id = parameters.get("memory_id")
        if not memory_id:
            return MCPToolResponse(success=False, error="Memory ID is required")
        
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.delete(
                f'http://ledger:{ledger_port}/memories/by-id/{memory_id}'
            )
            response.raise_for_status()
            result = response.json()
            
        return MCPToolResponse(success=True, result=result)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in memory delete: {e}")
        return MCPToolResponse(success=False, error=f"HTTP error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in memory delete: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _memory_list(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List memories via the ledger service."""
    try:
        limit = parameters.get("limit", 10)
        offset = parameters.get("offset", 0)
        
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f'http://ledger:{ledger_port}/memories',
                params={"limit": limit, "offset": offset}
            )
            response.raise_for_status()
            result = response.json()
            
        return MCPToolResponse(success=True, result=result)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in memory list: {e}")
        return MCPToolResponse(success=False, error=f"HTTP error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in memory list: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _memory_get(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Get a specific memory by ID via the ledger service."""
    try:
        memory_id = parameters.get("memory_id")
        if not memory_id:
            return MCPToolResponse(success=False, error="Memory ID is required")
        
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f'http://ledger:{ledger_port}/memories/by-id/{memory_id}'
            )
            response.raise_for_status()
            result = response.json()
            
        return MCPToolResponse(success=True, result=result)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in memory get: {e}")
        return MCPToolResponse(success=False, error=f"HTTP error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in memory get: {e}")
        return MCPToolResponse(success=False, error=str(e))
