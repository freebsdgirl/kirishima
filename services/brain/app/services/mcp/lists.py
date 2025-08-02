"""
MCP lists tool - Task list management operations via Google Tasks API.

This module provides task list management functionality via the MCP (Model Context Protocol) service.
It supports the following operations on Google Tasks lists:
- list_task_lists: List all available task lists (excluding stickynotes)
- create_task_list: Create a new task list
- delete_task_list: Delete a task list (cannot delete stickynotes)
- list_tasks: List tasks in a specific task list
- create_task: Create a task in a specific task list
- delete_task: Delete a task from a specific task list

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


def format_task_list_info(task_list: Dict[str, Any]) -> str:
    """
    Format task list information into a compact, token-efficient string.
    
    Args:
        task_list: Task list data from Google Tasks API
        
    Returns:
        str: Formatted task list string
    """
    list_id = task_list.get('id', 'N/A')
    title = task_list.get('title', 'Untitled')
    updated = task_list.get('updated', '')
    
    # Format update time
    if updated:
        updated_str = updated[:10] if len(updated) > 10 else updated
        return f"ID: {list_id} | Title: {title} | Updated: {updated_str}"
    else:
        return f"ID: {list_id} | Title: {title}"


def format_task_info(task: Dict[str, Any]) -> str:
    """
    Format task information into a compact, token-efficient string.
    
    Args:
        task: Task data from Google Tasks API
        
    Returns:
        str: Formatted task string
    """
    task_id = task.get('id', 'N/A')
    title = task.get('title', 'Untitled')
    status = task.get('status', 'needsAction')
    due_date = task.get('due', '')
    notes = task.get('notes', '')
    
    # Build formatted string
    parts = [f"ID: {task_id}", f"Title: {title}", f"Status: {status}"]
    
    if due_date:
        due_str = due_date[:10] if len(due_date) > 10 else due_date
        parts.append(f"Due: {due_str}")
    
    if notes and len(notes) > 0:
        # Truncate notes if too long
        notes_truncated = notes[:100] + "..." if len(notes) > 100 else notes
        parts.append(f"Notes: {notes_truncated}")
    
    return " | ".join(parts)


async def lists(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Task lists operations via MCP.
    Supports task list management and operations on tasks within specific lists.
    
    Actions:
    - list_task_lists: List all available task lists (excluding stickynotes)
    - create_task_list: Create a new task list (requires title)
    - delete_task_list: Delete a task list (requires task_list_id, cannot delete stickynotes)
    - list_tasks: List tasks in a specific task list (requires task_list_id)
    - create_task: Create task in specific task list (requires task_list_id, title)
    - delete_task: Delete task from specific task list (requires task_list_id, task_id)
    """
    try:
        action = parameters.get("action")
        if not action:
            return MCPToolResponse(success=False, result={}, error="Action is required")
        
        if action == "list_task_lists":
            return await _lists_list_task_lists(parameters)
        elif action == "create_task_list":
            return await _lists_create_task_list(parameters)
        elif action == "delete_task_list":
            return await _lists_delete_task_list(parameters)
        elif action == "list_tasks":
            return await _lists_list_tasks(parameters)
        elif action == "create_task":
            return await _lists_create_task(parameters)
        elif action == "delete_task":
            return await _lists_delete_task(parameters)
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


async def _lists_list_task_lists(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List all available task lists (excluding stickynotes)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists")
            response.raise_for_status()
            
            task_lists = response.json()
            
            if not task_lists:
                return MCPToolResponse(
                    success=True,
                    result={"message": "No task lists found", "count": 0},
                    error=None
                )
            
            # Format task lists as compact strings
            list_strings = [format_task_list_info(task_list) for task_list in task_lists]
            
            return MCPToolResponse(
                success=True,
                result={
                    "message": f"Found {len(task_lists)} task list(s)",
                    "count": len(task_lists),
                    "task_lists": list_strings
                },
                error=None
            )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error listing task lists: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list task lists: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error listing task lists: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list task lists: {str(e)}"
        )


async def _lists_create_task_list(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Create a new task list."""
    try:
        title = parameters.get("title")
        if not title:
            return MCPToolResponse(success=False, result={}, error="Title is required for create_task_list action")
        
        payload = {"title": title}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                task_list_id = result.get("data", {}).get("task_list_id")
                return MCPToolResponse(
                    success=True,
                    result={
                        "message": f"Successfully created task list: {title}",
                        "task_list_id": task_list_id
                    },
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to create task list")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating task list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create task list: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error creating task list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create task list: {str(e)}"
        )


async def _lists_delete_task_list(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Delete a task list (cannot delete stickynotes)."""
    try:
        task_list_id = parameters.get("task_list_id")
        if not task_list_id:
            return MCPToolResponse(success=False, result={}, error="task_list_id is required for delete_task_list action")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{task_list_id}")
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                return MCPToolResponse(
                    success=True,
                    result={"message": f"Successfully deleted task list: {task_list_id}"},
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to delete task list")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error deleting task list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete task list: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error deleting task list: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete task list: {str(e)}"
        )


async def _lists_list_tasks(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List tasks in a specific task list."""
    try:
        task_list_id = parameters.get("task_list_id")
        if not task_list_id:
            return MCPToolResponse(success=False, result={}, error="task_list_id is required for list_tasks action")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{task_list_id}/tasks")
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                tasks = result.get("data", [])
                
                if not tasks:
                    return MCPToolResponse(
                        success=True,
                        result={"message": "No tasks found in this task list", "count": 0},
                        error=None
                    )
                
                # Format tasks as compact strings
                task_strings = [format_task_info(task) for task in tasks]
                
                return MCPToolResponse(
                    success=True,
                    result={
                        "message": f"Found {len(tasks)} task(s) in task list",
                        "count": len(tasks),
                        "tasks": task_strings
                    },
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to list tasks")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error listing tasks: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list tasks: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list tasks: {str(e)}"
        )


async def _lists_create_task(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Create a task in a specific task list."""
    try:
        task_list_id = parameters.get("task_list_id")
        title = parameters.get("title")
        
        if not task_list_id:
            return MCPToolResponse(success=False, result={}, error="task_list_id is required for create_task action")
        if not title:
            return MCPToolResponse(success=False, result={}, error="title is required for create_task action")
        
        # Build request payload
        payload = {"title": title}
        
        # Optional fields
        if parameters.get("notes"):
            payload["notes"] = parameters["notes"]
        if parameters.get("due"):
            payload["due"] = parameters["due"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{task_list_id}/tasks", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                task_id = result.get("data", {}).get("task_id")
                return MCPToolResponse(
                    success=True,
                    result={
                        "message": f"Successfully created task: {title}",
                        "task_id": task_id
                    },
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to create task")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating task: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create task: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create task: {str(e)}"
        )


async def _lists_delete_task(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Delete a task from a specific task list."""
    try:
        task_list_id = parameters.get("task_list_id")
        task_id = parameters.get("task_id")
        
        if not task_list_id:
            return MCPToolResponse(success=False, result={}, error="task_list_id is required for delete_task action")
        if not task_id:
            return MCPToolResponse(success=False, result={}, error="task_id is required for delete_task action")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{GOOGLEAPI_BASE_URL}/tasks/tasklists/{task_list_id}/tasks/{task_id}")
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                return MCPToolResponse(
                    success=True,
                    result={"message": f"Successfully deleted task: {task_id}"},
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to delete task")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error deleting task: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete task: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete task: {str(e)}"
        )
