"""
This module provides the `execute_google_action` function, which executes parsed actions for Google services
such as Gmail, Calendar, and Contacts. It dispatches the action to the appropriate service handler based on
the specified service in the `GoogleServiceAction` object. The function supports options for returning slimmed-down
results and human-readable output. Errors during execution are logged and returned as HTTP exceptions.
Functions:
    execute_google_action(action: GoogleServiceAction, slim: bool = True, readable: bool = False) -> Dict[str, Any]:
        Executes a parsed Google service action and returns the result or raises an HTTPException on failure.
"""
from typing import Dict, Any
from fastapi import HTTPException
from shared.models.googleapi import (
    GoogleServiceAction
)

from app.services.nlp.execute_gmail_action import _execute_gmail_action
from app.services.nlp.execute_calendar_action import _execute_calendar_action
from app.services.nlp.execute_contacts_action import _execute_contacts_action

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")


async def execute_google_action(action: GoogleServiceAction, slim: bool = True, readable: bool = False) -> Dict[str, Any]:
    """
    Execute a parsed Google service action.
    
    Args:
        action: The parsed action to execute
        slim: If True, return only essential data to reduce token usage
        readable: If True, return human-readable text instead of JSON
        
    Returns:
        Dict containing the result of the action
        
    Raises:
        HTTPException: If action execution fails
    """
    service = action.service.lower()
    action_name = action.action.lower()
    params = action.parameters
    
    try:
        if service == "gmail":
            return await _execute_gmail_action(action_name, params, slim=slim, readable=readable)
        elif service == "calendar":
            return await _execute_calendar_action(action_name, params, slim=slim, readable=readable)
        elif service == "contacts":
            return await _execute_contacts_action(action_name, params, readable=readable)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown service: {service}"
            )
            
    except Exception as e:
        logger.error(f"Error executing {service}.{action_name}: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Error executing action: {str(e)}"
        )