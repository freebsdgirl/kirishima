"""
MCP lists tool - Simple list management operations via Google Tasks API.

This module provides simple list management functionality via the MCP (Model Context Protocol) service.
It supports the following operations using Google Tasks as a convenient CRUD interface:
- list_lists: List all available lists (excluding stickynotes)
- create_list: Create a new list
- delete_list: Delete a list (cannot delete stickynotes)  
- list_items: List items in a specific list
- add_item: Add an item to a specific list
- remove_item: Remove an item from a specific list

Each operation communicates with the googleapi service and returns a standardized
MCPToolResponse with user-friendly messages and token-efficient formatted strings.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any, List
import httpx
import os

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

# GoogleAPI service base URL
GOOGLEAPI_BASE_URL = os.getenv("GOOGLEAPI_BASE_URL", "http://googleapi:4215")


def format_list_info(task_list: Dict[str, Any]) -> str:
    """
    Format list information into a compact string.
    
    Args:
        task_list: Task list data from Google Tasks API
        
    Returns:
        str: Formatted string as "id|title"
    """
    list_id = task_list.get('id', 'N/A')
    title = task_list.get('title', 'Untitled')
    return f"{list_id}|{title}"


def format_item_info(item: Dict[str, Any]) -> str:
    """
    Format item information into a compact string.
    
    Args:
        item: Item data from Google Tasks API
        
    Returns:
        str: Formatted string as "id|title"
    """
    item_id = item.get('id', 'N/A')
    title = item.get('title', 'Untitled')
    return f"{item_id}|{title}"


async def lists(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    List management operations via MCP.
    Supports simple list management using Google Tasks API as a convenient CRUD interface.
    
    Actions:
    - list_lists: List all available lists (excluding stickynotes)
    - create_list: Create a new list (requires title)
    - delete_list: Delete a list (requires list_id, cannot delete stickynotes)
    - list_items: List items in a specific list (requires list_id)
    - add_item: Add item to specific list (requires list_id, title)
    - remove_item: Remove item from specific list (requires list_id, item_id)
    """
    try:
        action = parameters.get("action")
        if not action:
            return MCPToolResponse(success=False, result={}, error="Action is required")
        
        if action == "list_lists":
            return await _lists_list_lists(parameters)
        elif action == "create_list":
            return await _lists_create_list(parameters)
        elif action == "delete_list":
            return await _lists_delete_list(parameters)
        elif action == "list_items":
            return await _lists_list_items(parameters)
        elif action == "add_item":
            return await _lists_add_item(parameters)
        elif action == "remove_item":
            return await _lists_remove_item(parameters)
        else:
            return MCPToolResponse(
                success=False,
                result={},
                error=f"Unknown action: {action}"
            )
    
    except Exception as e:
        logger.error(f"Error in lists operation: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Lists operation failed: {str(e)}"
        )


async def _lists_list_lists(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List all available lists (excluding stickynotes)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists")
            response.raise_for_status()
            
            task_lists = response.json()
            
            if not task_lists:
                return MCPToolResponse(
                    success=True,
                    result=[],
                    error=None
                )
            
            # Format lists as compact strings
            list_strings = [format_list_info(task_list) for task_list in task_lists]
            
            return MCPToolResponse(
                success=True,
                result=list_strings,
                error=None
            )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error listing lists: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list lists: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error listing lists: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list lists: {str(e)}"
        )


async def _lists_create_list(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Create a new list."""
    try:
        title = parameters.get("title")
        if not title:
            return MCPToolResponse(success=False, result={}, error="Title is required for create_list action")
        
        payload = {"title": title}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                list_id = result.get("data", {}).get("task_list_id")
                return MCPToolResponse(
                    success=True,
                    result=f"{list_id}|{title}",
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to create list")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create list: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error creating list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create list: {str(e)}"
        )


async def _lists_delete_list(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Delete a list (cannot delete stickynotes)."""
    try:
        list_id = parameters.get("list_id")
        if not list_id:
            return MCPToolResponse(success=False, result={}, error="list_id is required for delete_list action")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{list_id}")
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                return MCPToolResponse(
                    success=True,
                    result=f"deleted|{list_id}",
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to delete list")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error deleting list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete list: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error deleting list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete list: {str(e)}"
        )


async def _lists_list_items(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List items in a specific list."""
    try:
        list_id = parameters.get("list_id")
        if not list_id:
            return MCPToolResponse(success=False, result={}, error="list_id is required for list_items action")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{list_id}/tasks")
            response.raise_for_status()
            
            # This endpoint returns List[TaskModel] directly, not the standard format
            items = response.json()
            
            if not items:
                return MCPToolResponse(
                    success=True,
                    result=[],
                    error=None
                )
            
            # Format items as compact strings  
            item_strings = [format_item_info(item) for item in items]
            
            return MCPToolResponse(
                success=True,
                result=item_strings,
                error=None
            )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error listing items: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list items: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error listing items: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list items: {str(e)}"
        )


async def _lists_add_item(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Add an item to a specific list."""
    try:
        list_id = parameters.get("list_id")
        title = parameters.get("title")
        
        if not list_id:
            return MCPToolResponse(success=False, result={}, error="list_id is required for add_item action")
        if not title:
            return MCPToolResponse(success=False, result={}, error="title is required for add_item action")
        
        # Build request payload (simplified for lists - just title)
        payload = {"title": title}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{list_id}/tasks", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                item_id = result.get("data", {}).get("task_id")
                return MCPToolResponse(
                    success=True,
                    result=f"{item_id}|{title}",
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to add item")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error adding item: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to add item: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error adding item: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to add item: {str(e)}"
        )


async def _lists_remove_item(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Remove an item from a specific list."""
    try:
        list_id = parameters.get("list_id")
        item_id = parameters.get("item_id")
        
        if not list_id:
            return MCPToolResponse(success=False, result={}, error="list_id is required for remove_item action")
        if not item_id:
            return MCPToolResponse(success=False, result={}, error="item_id is required for remove_item action")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{list_id}/tasks/{item_id}")
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                return MCPToolResponse(
                    success=True,
                    result=f"removed|{item_id}",
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to remove item")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error removing item: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to remove item: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error removing item: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to remove item: {str(e)}"
        )
