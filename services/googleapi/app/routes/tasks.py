"""
Google Tasks API routes.
Provides endpoints for task and task list management.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from fastapi import APIRouter, HTTPException
from typing import List

from shared.models.googleapi import (
    TaskModel, TaskListModel, CreateTaskRequest, UpdateTaskRequest,
    CreateTaskListRequest, TasksResponse, DueTasksResponse
)

from app.services.tasks.tasks import (
    create_task_list, list_task_lists, delete_task_list,
    create_task, list_stickynotes_tasks, list_tasks_in_list, update_task, 
    complete_task, delete_task, get_due_tasks
)
from app.services.tasks.auth import validate_tasks_access
from app.services.tasks.monitor import get_monitor_status

router = APIRouter()


# Task Lists Management

@router.post("/tasklists", response_model=TasksResponse)
async def create_new_task_list(request: CreateTaskListRequest):
    """Create a new task list."""
    return create_task_list(request)


@router.get("/tasklists", response_model=List[TaskListModel])
async def get_task_lists():
    """List all task lists (excluding stickynotes)."""
    return list_task_lists(exclude_stickynotes=True)


@router.delete("/tasklists/{task_list_id}", response_model=TasksResponse)
async def remove_task_list(task_list_id: str):
    """Delete a task list (cannot delete stickynotes)."""
    return delete_task_list(task_list_id)


# Task Management in Lists

@router.post("/tasklists/{task_list_id}/tasks", response_model=TasksResponse)
async def add_task_to_list(task_list_id: str, request: CreateTaskRequest):
    """Add a task to a specific task list."""
    request.task_list_id = task_list_id
    return create_task(request)


@router.get("/tasklists/{task_list_id}/tasks", response_model=List[TaskModel])
async def list_tasks_in_task_list(task_list_id: str):
    """List all tasks in a specific task list."""
    return list_tasks_in_list(task_list_id)


@router.delete("/tasklists/{task_list_id}/tasks/{task_id}", response_model=TasksResponse)
async def remove_task_from_list(task_list_id: str, task_id: str):
    """Remove a task from a specific task list."""
    return delete_task(task_id, task_list_id)


# Stickynotes (Default Task List) Management

@router.get("/stickynotes", response_model=List[TaskModel])
async def get_stickynotes_tasks():
    """List all tasks in the stickynotes task list."""
    return list_stickynotes_tasks()


@router.post("/stickynotes", response_model=TasksResponse)
async def create_stickynote_task(request: CreateTaskRequest):
    """Create a new task in the stickynotes task list."""
    return create_task(request)


@router.put("/stickynotes/{task_id}", response_model=TasksResponse)
async def update_stickynote_task(task_id: str, request: UpdateTaskRequest):
    """Update a task in the stickynotes task list."""
    return update_task(task_id, request)


@router.post("/stickynotes/{task_id}/complete", response_model=TasksResponse)
async def complete_stickynote_task(task_id: str):
    """Complete a task in the stickynotes task list (handles recurrence)."""
    return complete_task(task_id)


@router.delete("/stickynotes/{task_id}", response_model=TasksResponse)
async def delete_stickynote_task(task_id: str):
    """Delete a task from the stickynotes task list."""
    return delete_task(task_id)


# Due Tasks (Brain Service Endpoint)

@router.get("/due", response_model=DueTasksResponse)
async def get_current_due_tasks():
    """
    Get all due and overdue tasks from stickynotes.
    This endpoint is designed for the brain service to query.
    """
    return get_due_tasks()


# System/Status Endpoints

@router.get("/validate")
async def validate_access():
    """Validate Google Tasks API access."""
    return validate_tasks_access()


@router.get("/monitor/status")
async def get_tasks_monitor_status():
    """Get the current status of the tasks monitor."""
    return get_monitor_status()
