"""
This module provides service functions for managing Google Tasks via the Google Tasks API,
with additional support for Kirishima-specific metadata and recurrence logic.
Functions:
    - create_task_list(request: CreateTaskListRequest) -> TasksResponse:
    - list_task_lists(exclude_stickynotes: bool = True) -> List[TaskListModel]:
        List all task lists, optionally excluding the stickynotes list.
    - delete_task_list(task_list_id: str) -> TasksResponse:
        Delete a task list, except for the stickynotes list.
    - create_task(request: CreateTaskRequest) -> TasksResponse:
        Create a new task in a specified or default (stickynotes) task list, with Kirishima metadata.
    - list_stickynotes_tasks() -> List[TaskModel]:
        List all tasks in the stickynotes task list, parsing Kirishima metadata.
    - update_task(task_id: str, request: UpdateTaskRequest, task_list_id: Optional[str] = None) -> TasksResponse:
        Update an existing task, preserving and updating Kirishima metadata as needed.
    - complete_task(task_id: str, task_list_id: Optional[str] = None) -> TasksResponse:
        Complete a task, handling recurrence by updating the due date if an RRULE is present.
    - delete_task(task_id: str, task_list_id: Optional[str] = None) -> TasksResponse:
        Delete a task from a specified or default (stickynotes) task list.
    - get_due_tasks() -> DueTasksResponse:
        Retrieve all due and overdue tasks from the stickynotes task list, for use by the brain service.
Dependencies:
    - shared.log_config.get_logger
    - shared.models.googleapi (TaskModel, TaskListModel, CreateTaskRequest, UpdateTaskRequest, CreateTaskListRequest, TasksResponse, DueTasksResponse)
    - .auth.get_tasks_service
    - .util (get_stickynotes_tasklist_id, create_kirishima_metadata, parse_kirishima_metadata, calculate_next_due_date, is_task_due)
    - typing
    - datetime
All functions handle exceptions and log errors, returning structured response objects.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from shared.models.googleapi import (
    TaskModel, TaskListModel, CreateTaskRequest, UpdateTaskRequest,
    CreateTaskListRequest, TasksResponse, DueTasksResponse
)

from .auth import get_tasks_service
from .util import (
    get_stickynotes_tasklist_id, create_kirishima_metadata, 
    parse_kirishima_metadata, calculate_next_due_date, is_task_due
)

from typing import List, Optional, Dict, Any
from datetime import datetime


def create_task_list(request: CreateTaskListRequest) -> TasksResponse:
    """
    Create a new task list.
    
    Args:
        request: Task list creation request
        
    Returns:
        TasksResponse: Operation result
    """
    try:
        service = get_tasks_service()
        
        task_list_body = {
            'title': request.title
        }
        
        result = service.tasklists().insert(body=task_list_body).execute()
        
        logger.info(f"Created task list: {result['title']} ({result['id']})")
        
        return TasksResponse(
            success=True,
            message="Task list created successfully",
            data={
                "task_list_id": result['id'],
                "title": result['title']
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create task list: {e}")
        return TasksResponse(
            success=False,
            message=f"Failed to create task list: {str(e)}"
        )


def list_task_lists(exclude_stickynotes: bool = True) -> List[TaskListModel]:
    """
    List all task lists.
    
    Args:
        exclude_stickynotes: Whether to exclude the stickynotes task list
        
    Returns:
        List[TaskListModel]: List of task lists
    """
    try:
        service = get_tasks_service()
        result = service.tasklists().list().execute()
        task_lists = result.get('items', [])
        
        if exclude_stickynotes:
            # Filter out the stickynotes task list
            task_lists = [tl for tl in task_lists if tl.get('title', '').lower() != 'stickynotes']
        
        return [
            TaskListModel(
                id=tl['id'],
                title=tl['title'],
                updated=tl.get('updated')
            )
            for tl in task_lists
        ]
        
    except Exception as e:
        logger.error(f"Failed to list task lists: {e}")
        return []


def delete_task_list(task_list_id: str) -> TasksResponse:
    """
    Delete a task list (except stickynotes).
    
    Args:
        task_list_id: Task list ID to delete
        
    Returns:
        TasksResponse: Operation result
    """
    try:
        service = get_tasks_service()
        
        # Get task list details to check if it's stickynotes
        task_list = service.tasklists().get(tasklist=task_list_id).execute()
        
        if task_list.get('title', '').lower() == 'stickynotes':
            return TasksResponse(
                success=False,
                message="Cannot delete stickynotes task list"
            )
        
        service.tasklists().delete(tasklist=task_list_id).execute()
        
        logger.info(f"Deleted task list: {task_list['title']} ({task_list_id})")
        
        return TasksResponse(
            success=True,
            message="Task list deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to delete task list: {e}")
        return TasksResponse(
            success=False,
            message=f"Failed to delete task list: {str(e)}"
        )


def create_task(request: CreateTaskRequest) -> TasksResponse:
    """
    Create a new task.
    
    Args:
        request: Task creation request
        
    Returns:
        TasksResponse: Operation result
    """
    try:
        service = get_tasks_service()
        
        # Determine task list ID
        if request.task_list_id:
            task_list_id = request.task_list_id
        else:
            task_list_id = get_stickynotes_tasklist_id(service)
        
        # Create task notes with metadata
        notes = create_kirishima_metadata(
            due_time=request.due_time,
            rrule=request.rrule,
            user_notes=request.notes
        )
        
        # Build task body
        task_body = {
            'title': request.title,
            'notes': notes
        }
        
        # Add due date if provided
        if request.due:
            # Convert YYYY-MM-DD to RFC 3339 format
            due_datetime = f"{request.due}T00:00:00.000Z"
            task_body['due'] = due_datetime
        
        result = service.tasks().insert(
            tasklist=task_list_id,
            body=task_body
        ).execute()
        
        logger.info(f"Created task: {result['title']} ({result['id']})")
        
        return TasksResponse(
            success=True,
            message="Task created successfully",
            data={
                "task_id": result['id'],
                "title": result['title']
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        return TasksResponse(
            success=False,
            message=f"Failed to create task: {str(e)}"
        )


def list_stickynotes_tasks() -> List[TaskModel]:
    """
    List all tasks in the stickynotes task list.
    
    Returns:
        List[TaskModel]: List of tasks with parsed metadata
    """
    try:
        service = get_tasks_service()
        task_list_id = get_stickynotes_tasklist_id(service)
        
        result = service.tasks().list(
            tasklist=task_list_id,
            showCompleted=True,
            showHidden=True
        ).execute()
        
        tasks = result.get('items', [])
        task_models = []
        
        for task in tasks:
            # Parse Kirishima metadata
            user_notes, due_time, rrule = parse_kirishima_metadata(task.get('notes'))
            
            task_model = TaskModel(
                id=task['id'],
                title=task['title'],
                notes=user_notes,
                status=task.get('status', 'needsAction'),
                due=task.get('due'),
                completed=task.get('completed'),
                updated=task.get('updated'),
                kirishima_due_time=due_time,
                kirishima_rrule=rrule
            )
            task_models.append(task_model)
        
        return task_models
        
    except Exception as e:
        logger.error(f"Failed to list stickynotes tasks: {e}")
        return []


def update_task(task_id: str, request: UpdateTaskRequest, task_list_id: Optional[str] = None) -> TasksResponse:
    """
    Update an existing task.
    
    Args:
        task_id: Task ID to update
        request: Update request
        task_list_id: Task list ID (defaults to stickynotes)
        
    Returns:
        TasksResponse: Operation result
    """
    try:
        service = get_tasks_service()
        
        if not task_list_id:
            task_list_id = get_stickynotes_tasklist_id(service)
        
        # Get current task to preserve existing metadata
        current_task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
        current_notes, current_due_time, current_rrule = parse_kirishima_metadata(current_task.get('notes'))
        
        # Build update body
        task_body = {'id': task_id}  # Include task ID in body
        
        if request.title is not None:
            task_body['title'] = request.title
        
        if request.status is not None:
            task_body['status'] = request.status
        
        # Handle due date
        if request.due is not None:
            due_datetime = f"{request.due}T00:00:00.000Z"
            task_body['due'] = due_datetime
        
        # Handle notes and metadata
        final_notes = request.notes if request.notes is not None else current_notes
        final_due_time = request.due_time if request.due_time is not None else current_due_time
        final_rrule = request.rrule if request.rrule is not None else current_rrule
        
        # Create updated notes with metadata
        updated_notes = create_kirishima_metadata(
            due_time=final_due_time,
            rrule=final_rrule,
            user_notes=final_notes
        )
        task_body['notes'] = updated_notes
        
        result = service.tasks().update(
            tasklist=task_list_id,
            task=task_id,
            body=task_body
        ).execute()
        
        logger.info(f"Updated task: {result['title']} ({task_id})")
        
        return TasksResponse(
            success=True,
            message="Task updated successfully",
            data={
                "task_id": result['id'],
                "title": result['title']
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to update task: {e}")
        return TasksResponse(
            success=False,
            message=f"Failed to update task: {str(e)}"
        )


def complete_task(task_id: str, task_list_id: Optional[str] = None) -> TasksResponse:
    """
    Complete a task, handling recurrence if present.
    
    Args:
        task_id: Task ID to complete
        task_list_id: Task list ID (defaults to stickynotes)
        
    Returns:
        TasksResponse: Operation result
    """
    try:
        service = get_tasks_service()
        
        if not task_list_id:
            task_list_id = get_stickynotes_tasklist_id(service)
        
        # Get current task
        current_task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
        user_notes, due_time, rrule = parse_kirishima_metadata(current_task.get('notes'))
        
        # If task has recurrence, update due date instead of marking complete
        if rrule and current_task.get('due'):
            current_due = current_task['due'][:10]  # Extract YYYY-MM-DD
            next_due = calculate_next_due_date(current_due, rrule)
            
            if next_due:
                # Update due date
                next_due_datetime = f"{next_due}T00:00:00.000Z"
                
                task_body = {
                    'id': task_id,  # Include task ID in body
                    'due': next_due_datetime,
                    'status': 'needsAction'  # Reset to needsAction
                }
                
                result = service.tasks().update(
                    tasklist=task_list_id,
                    task=task_id,
                    body=task_body
                ).execute()
                
                logger.info(f"Updated recurring task due date: {current_task['title']} -> {next_due}")
                
                return TasksResponse(
                    success=True,
                    message=f"Recurring task updated - next due: {next_due}",
                    data={
                        "task_id": task_id,
                        "next_due": next_due,
                        "recurring": True
                    }
                )
        
        # Non-recurring task or no RRULE - mark as completed
        task_body = {
            'id': task_id,  # Include task ID in body
            'status': 'completed',
            'completed': datetime.utcnow().isoformat() + 'Z'
        }
        
        result = service.tasks().update(
            tasklist=task_list_id,
            task=task_id,
            body=task_body
        ).execute()
        
        logger.info(f"Completed task: {current_task['title']} ({task_id})")
        
        return TasksResponse(
            success=True,
            message="Task completed successfully",
            data={
                "task_id": task_id,
                "recurring": False
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to complete task: {e}")
        return TasksResponse(
            success=False,
            message=f"Failed to complete task: {str(e)}"
        )


def delete_task(task_id: str, task_list_id: Optional[str] = None) -> TasksResponse:
    """
    Delete a task.
    
    Args:
        task_id: Task ID to delete
        task_list_id: Task list ID (defaults to stickynotes)
        
    Returns:
        TasksResponse: Operation result
    """
    try:
        service = get_tasks_service()
        
        if not task_list_id:
            task_list_id = get_stickynotes_tasklist_id(service)
        
        # Get task details for logging
        task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
        
        service.tasks().delete(tasklist=task_list_id, task=task_id).execute()
        
        logger.info(f"Deleted task: {task['title']} ({task_id})")
        
        return TasksResponse(
            success=True,
            message="Task deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        return TasksResponse(
            success=False,
            message=f"Failed to delete task: {str(e)}"
        )


def get_due_tasks() -> DueTasksResponse:
    """
    Get all due and overdue tasks from stickynotes task list.
    This endpoint is designed for the brain service to query.
    
    Returns:
        DueTasksResponse: Due and overdue tasks
    """
    try:
        service = get_tasks_service()
        task_list_id = get_stickynotes_tasklist_id(service)
        
        # Get all incomplete tasks
        result = service.tasks().list(
            tasklist=task_list_id,
            showCompleted=False
        ).execute()
        
        tasks = result.get('items', [])
        due_tasks = []
        overdue_tasks = []
        
        current_date = datetime.now().date()
        
        for task in tasks:
            # Skip tasks without due dates
            if not task.get('due'):
                continue
            
            # Parse Kirishima metadata
            user_notes, due_time, rrule = parse_kirishima_metadata(task.get('notes'))
            
            # Check if task is due
            if is_task_due(task, due_time):
                task_model = TaskModel(
                    id=task['id'],
                    title=task['title'],
                    notes=user_notes,
                    status=task.get('status', 'needsAction'),
                    due=task.get('due'),
                    completed=task.get('completed'),
                    updated=task.get('updated'),
                    kirishima_due_time=due_time,
                    kirishima_rrule=rrule
                )
                
                # Determine if overdue or just due
                due_date = datetime.strptime(task['due'][:10], '%Y-%m-%d').date()
                if due_date < current_date:
                    overdue_tasks.append(task_model)
                else:
                    due_tasks.append(task_model)
        
        logger.info(f"Found {len(due_tasks)} due tasks and {len(overdue_tasks)} overdue tasks")
        
        return DueTasksResponse(
            success=True,
            due_tasks=due_tasks,
            overdue_tasks=overdue_tasks
        )
        
    except Exception as e:
        logger.error(f"Failed to get due tasks: {e}")
        return DueTasksResponse(
            success=False,
            due_tasks=[],
            overdue_tasks=[]
        )
