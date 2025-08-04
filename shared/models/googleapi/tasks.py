"""
Tasks-specific models for GoogleAPI service.
Contains request and response models for Google Tasks operations.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TaskListModel(BaseModel):
    """
    Model representing a Google Tasks task list.
    """
    id: str = Field(..., description="The task list ID")
    title: str = Field(..., description="The task list title/name")
    updated: Optional[str] = Field(None, description="Last update timestamp")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA",
                    "title": "Shopping List",
                    "updated": "2025-07-24T10:30:00.000Z"
                }
            ]
        }
    }


class TaskModel(BaseModel):
    """
    Model representing a Google Tasks task with Kirishima metadata support.
    """
    id: str = Field(..., description="The task ID")
    title: str = Field(..., description="The task title/content")
    notes: Optional[str] = Field(None, description="Task notes/details (may contain Kirishima metadata)")
    status: str = Field(..., description="Task status (needsAction, completed)")
    due: Optional[str] = Field(None, description="Due date in RFC 3339 format (date only)")
    completed: Optional[str] = Field(None, description="Completion timestamp")
    updated: Optional[str] = Field(None, description="Last update timestamp")
    
    # Parsed Kirishima metadata (extracted from notes)
    kirishima_due_time: Optional[str] = Field(None, description="Due time in HH:MM format (parsed from notes)")
    kirishima_rrule: Optional[str] = Field(None, description="RFC 5545 RRULE for recurrence (parsed from notes)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA",
                    "title": "Call dentist",
                    "status": "needsAction",
                    "due": "2025-07-25",
                    "kirishima_due_time": "14:30",
                    "kirishima_rrule": "FREQ=MONTHLY;INTERVAL=1"
                }
            ]
        }
    }


class CreateTaskListRequest(BaseModel):
    """
    Request model for creating a new task list.
    """
    title: str = Field(..., description="The title/name for the new task list")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Shopping List"
                }
            ]
        }
    }


class CreateTaskRequest(BaseModel):
    """
    Request model for creating a new task.
    """
    title: str = Field(..., description="The task title/content")
    notes: Optional[str] = Field(None, description="Additional task notes (separate from Kirishima metadata)")
    due: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    due_time: Optional[str] = Field(None, description="Due time in HH:MM format (24-hour)")
    rrule: Optional[str] = Field(None, description="RFC 5545 RRULE for recurrence (e.g., 'FREQ=DAILY;INTERVAL=1')")
    task_list_id: Optional[str] = Field(None, description="Task list ID (defaults to stickynotes list)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Call dentist",
                    "notes": "Schedule annual cleaning",
                    "due": "2025-07-25",
                    "due_time": "14:30",
                    "rrule": "FREQ=MONTHLY;INTERVAL=1"
                }
            ]
        }
    }


class UpdateTaskRequest(BaseModel):
    """
    Request model for updating an existing task.
    """
    title: Optional[str] = Field(None, description="The task title/content")
    notes: Optional[str] = Field(None, description="Additional task notes")
    due: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    due_time: Optional[str] = Field(None, description="Due time in HH:MM format (24-hour)")
    rrule: Optional[str] = Field(None, description="RFC 5545 RRULE for recurrence")
    status: Optional[str] = Field(None, description="Task status (needsAction, completed)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Call dentist - rescheduled",
                    "due": "2025-07-26",
                    "due_time": "15:00"
                }
            ]
        }
    }


class DueTasksResponse(BaseModel):
    """
    Response model for checking due tasks - designed for brain service consumption.
    """
    success: bool = Field(..., description="Whether the operation was successful")
    due_tasks: List[TaskModel] = Field(..., description="List of tasks that are due now")
    overdue_tasks: List[TaskModel] = Field(..., description="List of tasks that are overdue")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "due_tasks": [
                        {
                            "id": "MTIzNDU2Nzg5MDEyMzQ1Njc4OTA",
                            "title": "Call dentist",
                            "status": "needsAction",
                            "due": "2025-07-24",
                            "kirishima_due_time": "14:30"
                        }
                    ],
                    "overdue_tasks": []
                }
            ]
        }
    } 