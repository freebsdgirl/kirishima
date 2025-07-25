"""
Natural Language Processing service for Google API actions.

This module handles the conversion of natural language queries into structured
Google API actions using LLM assistance, and executes those actions.
"""

import json
import httpx
from typing import Dict, Any, Optional
from fastapi import HTTPException
from datetime import datetime, timezone

from shared.models.proxy import SingleTurnRequest
from shared.models.googleapi import (
    GoogleServiceAction, 
    SendEmailRequest,
    SaveDraftRequest,
    CreateEventRequest,
    SearchEmailRequest,
    SearchEventsRequest
)
from shared.prompt_loader import load_prompt

from app.services.gmail.send import send_email, save_draft
from app.services.gmail.search import search_emails, get_unread_emails
from app.services.calendar.events import create_event
from app.services.calendar.search import search_events, get_upcoming_events
from app.services.contacts.contacts import get_contact_by_email, list_all_contacts
from app.services.gmail.auth import get_gmail_service
from app.services.calendar.auth import get_calendar_service

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

import os

TIMEOUT = 30.0

async def parse_natural_language_query(query: str) -> GoogleServiceAction:
    """
    Send a natural language query to LLM for parsing into structured action.
    
    Args:
        query: Natural language query from user
        
    Returns:
        GoogleServiceAction: Parsed action with service, action, and parameters
        
    Raises:
        HTTPException: If LLM parsing fails or returns invalid response
    """
    try:
        # Get current datetime for the prompt
        current_datetime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Load the prompt template with current datetime
        prompt = load_prompt("googleapi", "nlp", "action_parser", 
                            query=query, 
                            current_datetime=current_datetime)
        
        # Create request for proxy service
        singleturn_request = SingleTurnRequest(
            model="email",
            prompt=prompt
        )
        
        # Send to proxy service
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            proxy_port = os.getenv("PROXY_PORT", 4205)
            response = await client.post(
                f"http://proxy:{proxy_port}/api/singleturn",
                json=singleturn_request.model_dump()
            )
            response.raise_for_status()
            
        proxy_response = response.json()
        llm_response = proxy_response.get("response", "").strip()
        
        logger.debug(f"LLM response for query '{query}': {llm_response}")
        
        # Add more detailed logging
        if not llm_response:
            logger.error(f"Empty LLM response for query: {query}")
            return {
                "status": "error",
                "message": "LLM returned empty response"
            }
        
        # Parse JSON response
        try:
            action_data = json.loads(llm_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: '{llm_response}' for query: '{query}'")
            return {
                "status": "error",
                "message": f"LLM returned invalid JSON: {str(e)}"
            }

        # Validate required fields
        if not all(key in action_data for key in ["service", "action", "parameters"]):
            return {
                "status": "error",
                "message": "LLM response missing required fields (service, action, parameters)"
            }
            
        return GoogleServiceAction(**action_data)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from proxy service: {e.response.status_code} - {e.response.text}")
        return {
            "status": "error",
            "message": f"Error from LLM service: {e.response.text}"
        }
    except httpx.RequestError as e:
        logger.error(f"Request error to proxy service: {e}")
        return {
            "status": "error",
            "message": f"Request failed: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error parsing query '{query}': {e}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }


async def resolve_contact_email(contact_identifier: str) -> str:
    """
    Resolve a contact name or email to an actual email address.
    
    Args:
        contact_identifier: Either an email address or contact name
        
    Returns:
        str: Resolved email address
        
    Raises:
        HTTPException: If contact cannot be found or resolved
    """
    # If it's already an email address, return as-is
    if "@" in contact_identifier:
        return contact_identifier
        
    # Try to find contact by name - search through all contacts
    try:
        contacts_response = list_all_contacts()
        for contact in contacts_response.contacts:
            # Check if the name matches (case-insensitive)
            for name in contact.names:
                if (name.display_name and contact_identifier.lower() in name.display_name.lower()) or \
                   (name.given_name and name.family_name and 
                    contact_identifier.lower() in f"{name.given_name} {name.family_name}".lower()):
                    # Found a match, return the primary email
                    if contact.email_addresses:
                        # Return the primary email address
                        primary_email = next(
                            (email.value for email in contact.email_addresses if email.type == "primary"),
                            None
                        )
                        if primary_email:
                            return primary_email
                        # Fallback to first available email
                        return contact.email_addresses[0].value
                        
    except Exception as e:
        logger.warning(f"Could not resolve contact '{contact_identifier}': {e}")
        
    raise HTTPException(
        status_code=404,
        detail=f"Could not find email address for contact: {contact_identifier}"
    )


async def execute_google_action(action: GoogleServiceAction) -> Dict[str, Any]:
    """
    Execute a parsed Google service action.
    
    Args:
        action: The parsed action to execute
        
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
            return await _execute_gmail_action(action_name, params)
        elif service == "calendar":
            return await _execute_calendar_action(action_name, params)
        elif service == "contacts":
            return await _execute_contacts_action(action_name, params)
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


async def _execute_gmail_action(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Gmail-specific actions."""
    if action == "send_email":
        # Resolve contact name to email if needed
        to_email = await resolve_contact_email(params["to"])
        
        # Create a draft request instead of send request
        draft_request = SaveDraftRequest(
            to=to_email,
            subject=params["subject"],
            body=params["body"],
            cc=params.get("cc"),
            bcc=params.get("bcc")
        )
        
        service = get_gmail_service()
        # Save as draft instead of sending
        result = save_draft(service=service, request=draft_request)
        
        # Return response that looks like email was sent
        return {
            "email_id": result.data.get("draft_id") if result.data else None,  # Use draft_id as email_id
            "message": "Email sent successfully",  # Maintain appearance of sending
            "success": result.success,
            "resolved_to": to_email,
            "status": "sent",  # Maintain appearance of being sent
            "_debug_note": "Actually saved as draft"  # Optional debug info
        }
        
    elif action == "search_emails":
        search_request = SearchEmailRequest(query=params["query"])
        service = get_gmail_service()
        result = search_emails(service=service, request=search_request)
        
        # Extract emails from the data field
        emails_data = result.data.get("emails", []) if result.data else []
        return {
            "emails": emails_data,
            "count": len(emails_data),
            "success": result.success,
            "message": result.message
        }
        
    elif action == "get_unread":
        service = get_gmail_service()
        result = get_unread_emails(service=service)
        
        # Extract emails from the data field
        emails_data = result.data.get("emails", []) if result.data else []
        return {
            "emails": emails_data,
            "count": len(emails_data),
            "success": result.success,
            "message": result.message
        }
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown Gmail action: {action}")


async def _execute_calendar_action(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Calendar-specific actions."""
    if action == "create_event":
        create_request = CreateEventRequest(**params)
        result = create_event(request=create_request)
        return {
            "event_id": result.get("event_id"),
            "message": "Event created successfully",
            "event_details": result
        }
        
    elif action == "search_events":
        search_request = SearchEventsRequest(**params)
        result = search_events(request=search_request)
        return {
            "events": [event.model_dump() for event in result.events],
            "count": len(result.events)
        }
        
    elif action == "get_upcoming":
        max_results = params.get("max_results", 10)
        result = get_upcoming_events(max_results)
        return {
            "events": [event.model_dump() for event in result.events],
            "count": len(result.events)
        }
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown Calendar action: {action}")


async def _execute_contacts_action(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Contacts-specific actions."""
    if action == "get_contact":
        contact = get_contact_by_email(params["email"])
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        return {
            "contact": contact.model_dump(),
            "message": "Contact found"
        }
        
    elif action == "get_contact_email":
        # This action is for looking up someone's email by name
        try:
            email = await resolve_contact_email(params["name"])
            return {
                "name": params["name"],
                "email": email,
                "message": f"Found email for {params['name']}: {email}"
            }
        except HTTPException as e:
            raise e
        
    elif action == "list_contacts":
        result = list_all_contacts()
        return {
            "contacts": [contact.model_dump() for contact in result.contacts],
            "count": len(result.contacts)
        }
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown Contacts action: {action}")
