"""
MCP stickynotes tool - Default task list operations via Google Tasks API.

This module provides stickynotes functionality via the MCP (Model Context Protocol) service.
It supports the following operations on the default Google Tasks list (stickynotes):
- list: List all tasks in the stickynotes list
- create: Create a new task with due date/time and RRULE support
- update: Update an existing task
- complete: Complete a task (handles recurring tasks automatically)
- delete: Delete a task

Each operation communicates with the googleapi service and returns a standardized
MCPToolResponse with user-friendly messages and token-efficient formatted strings.
Supports recurring tasks via RFC 5545 RRULE format.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any, List
import httpx
import os

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

# GoogleAPI service base URL
GOOGLEAPI_BASE_URL = os.getenv("GOOGLEAPI_BASE_URL", "http://googleapi:4215")


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
    due_time = task.get('kirishima_due_time', '')
    rrule = task.get('kirishima_rrule', '')
    notes = task.get('notes', '')
    
    # Build formatted string
    parts = [f"ID: {task_id}", f"Title: {title}", f"Status: {status}"]
    
    if due_date:
        due_str = due_date[:10] if len(due_date) > 10 else due_date
        if due_time:
            parts.append(f"Due: {due_str} at {due_time}")
        else:
            parts.append(f"Due: {due_str}")
    
    if rrule:
        parts.append(f"Recurring: {rrule}")
    
    if notes:
        # Truncate notes if too long
        notes_truncated = notes[:100] + "..." if len(notes) > 100 else notes
        parts.append(f"Notes: {notes_truncated}")
    
    return " | ".join(parts)


async def stickynotes(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Stickynotes operations via MCP.
    Supports list, create, update, complete, and delete operations on the default task list.
    
    Actions:
    - list: List all tasks in stickynotes (no parameters required)
    - create: Create a new task (requires title, optional due, due_time, rrule, notes)
    - update: Update a task (requires task_id, optional title, due, due_time, rrule, notes)
    - complete: Complete a task (requires task_id) - handles recurring tasks automatically
    - delete: Delete a task (requires task_id)
    """
    try:
        action = parameters.get("action")
        if not action:
            return MCPToolResponse(success=False, result={}, error="Action is required")
        
        if action == "list":
            return await _stickynotes_list(parameters)
        elif action == "create":
            return await _stickynotes_create(parameters)
        elif action == "update":
            return await _stickynotes_update(parameters)
        elif action == "complete":
            return await _stickynotes_complete(parameters)
        elif action == "delete":
            return await _stickynotes_delete(parameters)
        else:
            return MCPToolResponse(
                success=False,
                result={},
                error=f"Unknown action: {action}"
            )
    
    except Exception as e:
        logger.error(f"Error in stickynotes operation: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Stickynotes operation failed: {str(e)}"
        )


async def _stickynotes_list(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List all tasks in the stickynotes task list."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GOOGLEAPI_BASE_URL}/tasks/stickynotes")
            response.raise_for_status()
            
            tasks = response.json()
            
            if not tasks:
                return MCPToolResponse(
                    success=True,
                    result={"message": "No tasks found in stickynotes", "count": 0},
                    error=None
                )
            
            # Format tasks as compact strings
            task_strings = [format_task_info(task) for task in tasks]
            
            return MCPToolResponse(
                success=True,
                result={
                    "message": f"Found {len(tasks)} task(s) in stickynotes",
                    "count": len(tasks),
                    "tasks": task_strings
                },
                error=None
            )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error listing stickynotes: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list stickynotes: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error listing stickynotes: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to list stickynotes: {str(e)}"
        )


async def _stickynotes_create(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Create a new task in the stickynotes task list."""
    try:
        title = parameters.get("title")
        if not title:
            return MCPToolResponse(success=False, result={}, error="Title is required for create action")
        
        # Build request payload
        payload = {"title": title}
        
        # Optional fields
        if parameters.get("notes"):
            payload["notes"] = parameters["notes"]
        
        # Parse due field - can be YYYY-MM-DD or YYYY-MM-DD HH:MM
        if parameters.get("due"):
            due_str = parameters["due"]
            if " " in due_str:  # Contains time component
                try:
                    # Split date and time
                    date_part, time_part = due_str.split(" ", 1)
                    payload["due"] = date_part
                    payload["due_time"] = time_part
                except ValueError:
                    return MCPToolResponse(
                        success=False, 
                        result={}, 
                        error="Invalid due format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"
                    )
            else:  # Date only
                payload["due"] = due_str
        
        if parameters.get("rrule"):
            payload["rrule"] = parameters["rrule"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/tasks/stickynotes", json=payload)
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
        logger.error(f"HTTP error creating stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create task: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error creating stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to create task: {str(e)}"
        )


async def _stickynotes_update(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Update an existing task in the stickynotes task list."""
    try:
        task_id = parameters.get("task_id")
        if not task_id:
            return MCPToolResponse(success=False, result={}, error="task_id is required for update action")
        
        # Build request payload with only provided fields
        payload = {}
        
        if parameters.get("title"):
            payload["title"] = parameters["title"]
        if parameters.get("notes"):
            payload["notes"] = parameters["notes"]
        
        # Parse due field - can be YYYY-MM-DD or YYYY-MM-DD HH:MM
        if parameters.get("due"):
            due_str = parameters["due"]
            if " " in due_str:  # Contains time component
                try:
                    # Split date and time
                    date_part, time_part = due_str.split(" ", 1)
                    payload["due"] = date_part
                    payload["due_time"] = time_part
                except ValueError:
                    return MCPToolResponse(
                        success=False, 
                        result={}, 
                        error="Invalid due format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"
                    )
            else:  # Date only
                payload["due"] = due_str
        
        if parameters.get("rrule"):
            payload["rrule"] = parameters["rrule"]
        
        if not payload:
            return MCPToolResponse(
                success=False,
                result={},
                error="At least one field (title, notes, due, due_time, rrule) must be provided for update"
            )
        
        async with httpx.AsyncClient() as client:
            response = await client.put(f"{GOOGLEAPI_BASE_URL}/tasks/stickynotes/{task_id}", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                return MCPToolResponse(
                    success=True,
                    result={"message": f"Successfully updated task: {task_id}"},
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to update task")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error updating stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to update task: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error updating stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to update task: {str(e)}"
        )


async def _stickynotes_complete(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Complete a task in the stickynotes task list (handles recurring tasks automatically)."""
    try:
        task_id = parameters.get("task_id")
        if not task_id:
            return MCPToolResponse(success=False, result={}, error="task_id is required for complete action")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/tasks/stickynotes/{task_id}/complete")
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                message = result.get("message", f"Successfully completed task: {task_id}")
                return MCPToolResponse(
                    success=True,
                    result={"message": message},
                    error=None
                )
            else:
                return MCPToolResponse(
                    success=False,
                    result={},
                    error=result.get("message", "Failed to complete task")
                )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error completing stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to complete task: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error completing stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to complete task: {str(e)}"
        )


async def _stickynotes_delete(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Delete a task from the stickynotes task list."""
    try:
        task_id = parameters.get("task_id")
        if not task_id:
            return MCPToolResponse(success=False, result={}, error="task_id is required for delete action")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{GOOGLEAPI_BASE_URL}/tasks/stickynotes/{task_id}")
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
        logger.error(f"HTTP error deleting stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete task: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error deleting stickynote: {e}")
        return MCPToolResponse(
            success=False,
            result={},
            error=f"Failed to delete task: {str(e)}"
        )
