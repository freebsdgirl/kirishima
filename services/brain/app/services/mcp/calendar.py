"""
MCP calendar tool - Calendar operations via the googleapi service.

This module provides calendar functionality via the MCP (Model Context Protocol) service.
It supports the following operations on calendar events:
- create_event: Create a new calendar event
- search_events: Search for events using text/date criteria
- get_upcoming: Get upcoming events
- delete_event: Delete a calendar event
- list_events: List events within a date range

Each operation communicates with the googleapi service and returns a standardized
MCPToolResponse with user-friendly messages rather than raw data dumps.
Logging is provided for error handling and debugging purposes.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any
import httpx
import os

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


async def calendar(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Calendar operations via MCP.
    Supports create_event, search_events, get_upcoming, delete_event, and list_events operations.
    
    Actions:
    - create_event: Create a new calendar event (requires summary, start_datetime, end_datetime)
    - search_events: Search for events (optional query, start_date, end_date, max_results)
    - get_upcoming: Get upcoming events (optional max_results, days_ahead)
    - delete_event: Delete a calendar event (requires event_id, optional send_notifications)
    - list_events: List events within date range (requires start_date, end_date, optional max_results)
    """
    try:
        action = parameters.get("action")
        if not action:
            return MCPToolResponse(success=False, result={}, error="Action is required")
        
        if action == "create_event":
            return await _calendar_create_event(parameters)
        elif action == "search_events":
            return await _calendar_search_events(parameters)
        elif action == "get_upcoming":
            return await _calendar_get_upcoming(parameters)
        elif action == "delete_event":
            return await _calendar_delete_event(parameters)
        elif action == "list_events":
            return await _calendar_list_events(parameters)
        else:
            return MCPToolResponse(success=False, result={}, error=f"Unknown action: {action}")
    
    except Exception as e:
        logger.error(f"Calendar tool error: {e}")
        return MCPToolResponse(success=False, result={}, error=str(e))


async def _calendar_create_event(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Create a new calendar event."""
    try:
        summary = parameters.get("summary")
        start_datetime = parameters.get("start_datetime")
        end_datetime = parameters.get("end_datetime")
        
        if not summary or not start_datetime or not end_datetime:
            return MCPToolResponse(success=False, result={}, error="summary, start_datetime, and end_datetime are required for creating events")
        
        # Get googleapi service port from environment
        googleapi_port = os.getenv("GOOGLEAPI_PORT", 4215)
        googleapi_url = f"http://googleapi:{googleapi_port}"
        
        # Prepare request payload
        payload = {
            "summary": summary,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime
        }
        
        # Add optional fields if provided
        description = parameters.get("description")
        if description:
            payload["description"] = description
            
        location = parameters.get("location")
        if location:
            payload["location"] = location
            
        attendees = parameters.get("attendees")
        if attendees:
            payload["attendees"] = attendees
            
        send_notifications = parameters.get("send_notifications")
        if send_notifications is not None:
            payload["send_notifications"] = send_notifications
            
        transparency = parameters.get("transparency")
        if transparency:
            payload["transparency"] = transparency
            
        visibility = parameters.get("visibility")
        if visibility:
            payload["visibility"] = visibility
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{googleapi_url}/calendar/events", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                event_id = result.get("data", {}).get("event_id", "unknown")
                logger.info(f"Calendar event created successfully: {event_id}")
                message = f"Calendar event '{summary}' created successfully! Event ID: {event_id}. Scheduled for {start_datetime} to {end_datetime}."
                return MCPToolResponse(success=True, result={"status": "success", "message": message, "event_id": event_id})
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"Failed to create calendar event: {error_msg}")
                return MCPToolResponse(success=False, result={}, error=f"Failed to create calendar event: {error_msg}")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating calendar event: {e.response.status_code} - {e.response.text}")
        return MCPToolResponse(success=False, result={}, error=f"HTTP error creating calendar event: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error creating calendar event: {e}")
        return MCPToolResponse(success=False, result={}, error=f"Error connecting to calendar service: {str(e)}")
    except Exception as e:
        logger.error(f"Error in calendar create_event: {e}")
        return MCPToolResponse(success=False, result={}, error=str(e))


async def _calendar_search_events(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Search for calendar events."""
    try:
        # Get googleapi service port from environment
        googleapi_port = os.getenv("GOOGLEAPI_PORT", 4215)
        googleapi_url = f"http://googleapi:{googleapi_port}"
        
        # Prepare request payload
        payload = {}
        
        # Add optional parameters
        query = parameters.get("query")
        if query:
            payload["q"] = query
            
        start_date = parameters.get("start_date")
        if start_date:
            # Convert YYYY-MM-DD to ISO 8601 format if needed
            if "T" not in start_date:
                start_date += "T00:00:00Z"
            payload["time_min"] = start_date
            
        end_date = parameters.get("end_date")
        if end_date:
            # Convert YYYY-MM-DD to ISO 8601 format if needed
            if "T" not in end_date:
                end_date += "T23:59:59Z"
            payload["time_max"] = end_date
            
        max_results = parameters.get("max_results", 10)
        payload["max_results"] = max_results
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{googleapi_url}/calendar/events/search", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("events") is not None:
                events = result.get("events", [])
                count = len(events)
                logger.info(f"Calendar search returned {count} results")
                
                # Return compact summary instead of full event data
                if count == 0:
                    message = f"No calendar events found"
                    if query:
                        message += f" matching query: '{query}'"
                    if start_date or end_date:
                        date_range = []
                        if start_date:
                            date_range.append(f"from {start_date}")
                        if end_date:
                            date_range.append(f"to {end_date}")
                        message += f" {' '.join(date_range)}"
                else:
                    message = f"Found {count} calendar events"
                    if query:
                        message += f" matching query: '{query}'"
                    
                    # Add a brief summary of first few results
                    if count > 0:
                        summary_items = []
                        for event in events[:3]:  # Show first 3
                            summary = event.get("summary", "No title")[:50]
                            start = event.get("start", {})
                            start_time = start.get("dateTime") or start.get("date", "Unknown time")
                            summary_items.append(f"- {summary} ({start_time})")
                        if len(summary_items) > 0:
                            message += f"\n\nFirst {len(summary_items)} results:\n" + "\n".join(summary_items)
                        if count > 3:
                            message += f"\n... and {count - 3} more"
                
                return MCPToolResponse(success=True, result={"status": "success", "message": message, "count": count})
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"Failed to search calendar events: {error_msg}")
                return MCPToolResponse(success=False, result={}, error=f"Failed to search calendar events: {error_msg}")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error searching calendar events: {e.response.status_code} - {e.response.text}")
        return MCPToolResponse(success=False, result={}, error=f"HTTP error searching calendar events: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error searching calendar events: {e}")
        return MCPToolResponse(success=False, result={}, error=f"Error connecting to calendar service: {str(e)}")
    except Exception as e:
        logger.error(f"Error in calendar search_events: {e}")
        return MCPToolResponse(success=False, result={}, error=str(e))


async def _calendar_get_upcoming(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Get upcoming calendar events."""
    try:
        # Get googleapi service port from environment
        googleapi_port = os.getenv("GOOGLEAPI_PORT", 4215)
        googleapi_url = f"http://googleapi:{googleapi_port}"
        
        # Prepare request parameters
        params = {}
        
        max_results = parameters.get("max_results", 10)
        params["max_results"] = max_results
        
        days_ahead = parameters.get("days_ahead", 7)
        params["days_ahead"] = days_ahead
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{googleapi_url}/calendar/events/upcoming", params=params)
            response.raise_for_status()
            
            # Check if response is a list (direct event list) or has events field
            data = response.json()
            if isinstance(data, list):
                events = data
            else:
                events = data.get("events", data)
                
            count = len(events)
            logger.info(f"Retrieved {count} upcoming calendar events")
            
            # Return compact summary instead of full event data
            message = f"Retrieved {count} upcoming calendar events"
            if count > 0:
                # Add a brief summary of results
                summary_items = []
                for event in events[:5]:  # Show first 5
                    summary = event.get("summary", "No title")[:50]
                    start = event.get("start", {})
                    start_time = start.get("dateTime") or start.get("date", "Unknown time")
                    summary_items.append(f"- {summary} ({start_time})")
                message += f"\n\nUpcoming events:\n" + "\n".join(summary_items)
                if count > 5:
                    message += f"\n... and {count - 5} more"
            
            return MCPToolResponse(success=True, result={"status": "success", "message": message, "count": count})
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error getting upcoming calendar events: {e.response.status_code} - {e.response.text}")
        return MCPToolResponse(success=False, result={}, error=f"HTTP error getting upcoming calendar events: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error getting upcoming calendar events: {e}")
        return MCPToolResponse(success=False, result={}, error=f"Error connecting to calendar service: {str(e)}")
    except Exception as e:
        logger.error(f"Error in calendar get_upcoming: {e}")
        return MCPToolResponse(success=False, result={}, error=str(e))


async def _calendar_delete_event(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Delete a calendar event."""
    try:
        event_id = parameters.get("event_id")
        if not event_id:
            return MCPToolResponse(success=False, result={}, error="event_id is required for deleting events")
        
        # Get googleapi service port from environment
        googleapi_port = os.getenv("GOOGLEAPI_PORT", 4215)
        googleapi_url = f"http://googleapi:{googleapi_port}"
        
        # Prepare request parameters
        params = {}
        
        send_notifications = parameters.get("send_notifications", True)
        params["send_notifications"] = send_notifications
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(f"{googleapi_url}/calendar/events/{event_id}", params=params)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                logger.info(f"Calendar event deleted successfully: {event_id}")
                message = f"Calendar event deleted successfully! Event ID: {event_id}."
                return MCPToolResponse(success=True, result={"status": "success", "message": message, "event_id": event_id})
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"Failed to delete calendar event: {error_msg}")
                return MCPToolResponse(success=False, result={}, error=f"Failed to delete calendar event: {error_msg}")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error deleting calendar event: {e.response.status_code} - {e.response.text}")
        return MCPToolResponse(success=False, result={}, error=f"HTTP error deleting calendar event: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error deleting calendar event: {e}")
        return MCPToolResponse(success=False, result={}, error=f"Error connecting to calendar service: {str(e)}")
    except Exception as e:
        logger.error(f"Error in calendar delete_event: {e}")
        return MCPToolResponse(success=False, result={}, error=str(e))


async def _calendar_list_events(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List calendar events within a date range."""
    try:
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        
        if not start_date or not end_date:
            return MCPToolResponse(success=False, result={}, error="start_date and end_date are required for listing events")
        
        # Get googleapi service port from environment
        googleapi_port = os.getenv("GOOGLEAPI_PORT", 4215)
        googleapi_url = f"http://googleapi:{googleapi_port}"
        
        # Prepare request parameters
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        max_results = parameters.get("max_results", 100)
        params["max_results"] = max_results
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{googleapi_url}/calendar/events/date-range", params=params)
            response.raise_for_status()
            
            # Check if response is a list (direct event list) or has events field
            data = response.json()
            if isinstance(data, list):
                events = data
            else:
                events = data.get("events", data)
                
            count = len(events)
            logger.info(f"Retrieved {count} calendar events for date range {start_date} to {end_date}")
            
            # Return compact summary instead of full event data
            message = f"Found {count} calendar events from {start_date} to {end_date}"
            if count > 0:
                # Add a brief summary of results
                summary_items = []
                for event in events[:5]:  # Show first 5
                    summary = event.get("summary", "No title")[:50]
                    start = event.get("start", {})
                    start_time = start.get("dateTime") or start.get("date", "Unknown time")
                    summary_items.append(f"- {summary} ({start_time})")
                message += f"\n\nEvents in range:\n" + "\n".join(summary_items)
                if count > 5:
                    message += f"\n... and {count - 5} more"
            
            return MCPToolResponse(success=True, result={"status": "success", "message": message, "count": count})
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error listing calendar events: {e.response.status_code} - {e.response.text}")
        return MCPToolResponse(success=False, result={}, error=f"HTTP error listing calendar events: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error listing calendar events: {e}")
        return MCPToolResponse(success=False, result={}, error=f"Error connecting to calendar service: {str(e)}")
    except Exception as e:
        logger.error(f"Error in calendar list_events: {e}")
        return MCPToolResponse(success=False, result={}, error=str(e))
