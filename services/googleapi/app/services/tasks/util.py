"""
Utility functions for handling Google Tasks integration with Kirishima metadata.
This module provides helper functions for:
- Loading configuration from a JSON file.
- Retrieving the 'stickynotes' task list ID from Google Tasks.
- Embedding and parsing Kirishima-specific metadata (such as due time and recurrence rules) in task notes.
- Calculating the next due date for recurring tasks using RRULE.
- Determining if a task is currently due, considering optional due time.
Functions:
    get_config() -> Dict[str, Any]:
    get_stickynotes_tasklist_id(service) -> str:
    create_kirishima_metadata(due_time: Optional[str] = None, rrule: Optional[str] = None, user_notes: Optional[str] = None) -> str:
    parse_kirishima_metadata(notes: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    calculate_next_due_date(current_due: str, rrule_str: str) -> Optional[str]:
    is_task_due(task: Dict[str, Any], due_time: Optional[str] = None) -> bool:
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dateutil.rrule import rrule, rrulestr
from dateutil.parser import parse

def get_config() -> Dict[str, Any]:
    """
    Load configuration from config.json.
    
    Returns:
        dict: Configuration dictionary
    """
    try:
        with open('/app/config/config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


def get_stickynotes_tasklist_id(service) -> str:
    """
    Get the task list ID for the 'stickynotes' task list (default task list).
    If it doesn't exist or isn't renamed, uses the default task list.
    
    Args:
        service: Google Tasks service instance
        
    Returns:
        str: Task list ID for stickynotes
    """
    try:
        result = service.tasklists().list().execute()
        task_lists = result.get('items', [])
        
        # Look for a task list named 'stickynotes'
        for task_list in task_lists:
            if task_list.get('title', '').lower() == 'stickynotes':
                logger.info(f"Found stickynotes task list: {task_list['id']}")
                return task_list['id']
        
        # If no 'stickynotes' list found, use the first task list (usually @default)
        if task_lists:
            default_id = task_lists[0]['id']
            logger.info(f"Using default task list as stickynotes: {default_id}")
            return default_id
        
        # This shouldn't happen, but handle the case
        raise Exception("No task lists found")
        
    except Exception as e:
        logger.error(f"Failed to get stickynotes task list ID: {e}")
        raise


def create_kirishima_metadata(due_time: Optional[str] = None, rrule: Optional[str] = None, user_notes: Optional[str] = None) -> str:
    """
    Create task notes with embedded Kirishima metadata.
    
    Args:
        due_time: Due time in HH:MM format
        rrule: RFC 5545 RRULE string
        user_notes: User-provided notes
        
    Returns:
        str: Formatted notes with metadata
    """
    metadata = {}
    
    if due_time:
        metadata['due_time'] = due_time
    if rrule:
        metadata['rrule'] = rrule
    
    # Only add metadata if we have some
    if not metadata:
        return user_notes or ""
    
    metadata['kirishima'] = True
    
    # Format: user notes (if any) + JSON metadata
    notes_parts = []
    if user_notes:
        notes_parts.append(user_notes)
    
    notes_parts.append(f"KIRISHIMA_METADATA: {json.dumps(metadata)}")
    
    return "\n".join(notes_parts)


def parse_kirishima_metadata(notes: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse Kirishima metadata from task notes.
    
    Args:
        notes: Task notes string
        
    Returns:
        tuple: (user_notes, due_time, rrule)
    """
    if not notes:
        return None, None, None
    
    # Look for metadata marker
    metadata_marker = "KIRISHIMA_METADATA: "
    if metadata_marker not in notes:
        return notes, None, None
    
    try:
        # Split notes and metadata
        parts = notes.split(metadata_marker)
        user_notes = parts[0].strip() if parts[0].strip() else None
        metadata_json = parts[1].strip()
        
        # Parse metadata
        metadata = json.loads(metadata_json)
        
        if not metadata.get('kirishima'):
            return notes, None, None
        
        due_time = metadata.get('due_time')
        rrule = metadata.get('rrule')
        
        return user_notes, due_time, rrule
        
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Failed to parse Kirishima metadata: {e}")
        return notes, None, None


def calculate_next_due_date(current_due: str, rrule_str: str) -> Optional[str]:
    """
    Calculate the next due date based on RRULE.
    
    Args:
        current_due: Current due date in YYYY-MM-DD format
        rrule_str: RFC 5545 RRULE string
        
    Returns:
        str: Next due date in YYYY-MM-DD format, or None if error
    """
    try:
        # Parse current due date
        current_date = datetime.strptime(current_due, '%Y-%m-%d').date()
        
        # Parse RRULE
        rule = rrulestr(rrule_str, dtstart=datetime.combine(current_date, datetime.min.time()))
        
        # Get the next occurrence after current date
        next_occurrence = rule.after(datetime.combine(current_date, datetime.min.time()))
        
        if next_occurrence:
            return next_occurrence.strftime('%Y-%m-%d')
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to calculate next due date: {e}")
        return None


def is_task_due(task: Dict[str, Any], due_time: Optional[str] = None) -> bool:
    """
    Check if a task is due based on current time.
    
    Args:
        task: Google Tasks task dictionary
        due_time: Optional due time in HH:MM format
        
    Returns:
        bool: True if task is due
    """
    try:
        if not task.get('due'):
            return False
        
        # Parse due date
        due_date_str = task['due'][:10]  # Extract YYYY-MM-DD part
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        
        current_date = datetime.now().date()
        current_time = datetime.now().time()
        
        # If task is overdue (past due date)
        if due_date < current_date:
            return True
        
        # If task is due today
        if due_date == current_date:
            # If no specific time, consider it due all day
            if not due_time:
                return True
            
            # Check if specific time has passed
            try:
                due_time_obj = datetime.strptime(due_time, '%H:%M').time()
                return current_time >= due_time_obj
            except ValueError:
                # Invalid time format, treat as due all day
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to check if task is due: {e}")
        return False
