"""
This module provides the `_execute_calendar_action` asynchronous function to handle various Google Calendar-related actions
such as creating, searching, listing, and deleting events. It acts as a dispatcher for calendar operations, mapping action
strings and parameters to the appropriate service functions and formatting the results as needed.
Functions:
    _execute_calendar_action(action: str, params: Dict[str, Any], slim: bool = True, readable: bool = False) -> Dict[str, Any]:
        Executes a specified calendar action with the provided parameters.
        Supported actions:
            - "create_event": Creates a new calendar event.
            - "search_events": Searches for events based on parameters such as date range, keywords, etc.
            - "get_upcoming": Retrieves a list of upcoming events.
            - "delete_event": Deletes a specified event.
            - "list_events": Lists events within a specified date range.
        Parameters:
            action (str): The calendar action to execute.
            params (Dict[str, Any]): Parameters required for the action.
            slim (bool, optional): If True, returns a simplified event structure. Defaults to True.
            readable (bool, optional): If True, returns a human-readable summary. Defaults to False.
        Returns:
            Dict[str, Any]: The result of the calendar action, formatted according to the options provided.
        Raises:
            HTTPException: If an unknown action is specified or required parameters are missing.
"""

from typing import Dict, Any
from fastapi import HTTPException
from shared.models.googleapi import (
    CreateEventRequest,
    SearchEventsRequest
)

from app.services.text_formatter import clean_html_from_text, format_events_readable
from app.services.calendar.events import create_event, delete_event
from app.services.calendar.search import search_events, get_upcoming_events, get_events_by_date_range

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")


async def _execute_calendar_action(action: str, params: Dict[str, Any], slim: bool = True, readable: bool = False) -> Dict[str, Any]:
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
        # Map start_date/end_date parameters to time_min/time_max for SearchEventsRequest
        mapped_params = {}
        
        if "start_date" in params:
            # Convert YYYY-MM-DD to ISO 8601 format with timezone
            start_date = params["start_date"]
            if "T" not in start_date:
                start_date += "T00:00:00Z"
            mapped_params["time_min"] = start_date
            
        if "end_date" in params:
            # Convert YYYY-MM-DD to ISO 8601 format with timezone
            end_date = params["end_date"]
            if "T" not in end_date:
                end_date += "T23:59:59Z"
            mapped_params["time_max"] = end_date
            
        # Copy other parameters
        for key, value in params.items():
            if key not in ["start_date", "end_date"]:
                mapped_params[key] = value
        
        search_request = SearchEventsRequest(**mapped_params)
        result = search_events(request=search_request)
        
        # Convert events to dictionaries for processing
        events_list = [event.model_dump() for event in result.events]
        
        if readable:
            # Return human-readable format
            readable_text = format_events_readable(events_list)
            return {
                "result": readable_text,
                "count": len(events_list)
            }
        elif slim:
            # Return only essential event fields
            slim_events = []
            for event_dict in events_list:
                # Clean HTML from description
                description = event_dict.get("description")
                if description:
                    description = clean_html_from_text(description)
                
                slim_event = {
                    "id": event_dict.get("id"),
                    "summary": event_dict.get("summary"),
                    "start": event_dict.get("start"),
                    "end": event_dict.get("end"),
                    "location": event_dict.get("location"),
                    "description": description,
                    "status": event_dict.get("status"),
                    "attendees": event_dict.get("attendees", [])
                }
                slim_events.append(slim_event)
            
            return {
                "events": slim_events,
                "count": len(slim_events)
            }
        else:
            return {
                "events": events_list,
                "count": len(events_list)
            }
        
    elif action == "get_upcoming":
        max_results = params.get("max_results", 10)
        result = get_upcoming_events(max_results)
        
        # Convert events to dictionaries for processing
        events_list = [event.model_dump() for event in result.events]
        
        if readable:
            # Return human-readable format
            readable_text = format_events_readable(events_list)
            return {
                "result": readable_text,
                "count": len(events_list)
            }
        elif slim:
            # Return only essential event fields
            slim_events = []
            for event_dict in events_list:
                # Clean HTML from description
                description = event_dict.get("description")
                if description:
                    description = clean_html_from_text(description)
                
                slim_event = {
                    "id": event_dict.get("id"),
                    "summary": event_dict.get("summary"),
                    "start": event_dict.get("start"),
                    "end": event_dict.get("end"),
                    "location": event_dict.get("location"),
                    "description": description,
                    "status": event_dict.get("status"),
                    "attendees": event_dict.get("attendees", [])
                }
                slim_events.append(slim_event)
            
            return {
                "events": slim_events,
                "count": len(slim_events)
            }
        else:
            return {
                "events": events_list,
                "count": len(events_list)
            }
        
    elif action == "delete_event":
        event_id = params["event_id"]
        send_notifications = params.get("send_notifications", True)
        result = delete_event(event_id=event_id, send_notifications=send_notifications)
        return {
            "deleted": result,
            "event_id": event_id,
            "message": "Event deleted successfully" if result else "Failed to delete event"
        }
        
    elif action == "list_events":
        start_date = params["start_date"]
        end_date = params["end_date"]
        max_results = params.get("max_results", 100)
        
        # Convert date-only format to full ISO 8601 datetime format if needed
        if len(start_date) == 10:  # YYYY-MM-DD format
            start_date = f"{start_date}T00:00:00Z"
        if len(end_date) == 10:  # YYYY-MM-DD format
            end_date = f"{end_date}T23:59:59Z"
        
        events = get_events_by_date_range(
            start_date=start_date,
            end_date=end_date,
            max_results=max_results
        )
        
        return {
            "events": [event.model_dump() for event in events],
            "count": len(events),
            "date_range": {
                "start": start_date,
                "end": end_date
            }
        }
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown Calendar action: {action}")