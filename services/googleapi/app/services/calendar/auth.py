"""
Authentication utilities for accessing the Google Calendar API using OAuth2 credentials.

This module provides authentication functions for the Calendar API, reusing the same
OAuth2 credentials as Gmail since they're both Google APIs under the same project.

Functions:
    get_calendar_service():
        Loads OAuth2 credentials from a token file, refreshes them if expired, 
        and returns an authenticated Calendar API service instance.
    get_calendar_id():
        Retrieves the default calendar ID from configuration or discovers it automatically.

Logging:
    Uses a shared logger for error and status reporting.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.gmail.util import get_config
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import base64
import os
import json


def get_calendar_service():
    """
    Load OAuth2 credentials and return an authenticated Calendar service.
    
    Returns:
        googleapiclient.discovery.Resource: Authenticated Calendar service
        
    Raises:
        FileNotFoundError: If token file doesn't exist
        Exception: If credentials are invalid or expired
    """
    config = get_config()
    token_path = config.get('gmail', {}).get('token_path', '/app/config/token.json')
    
    if not os.path.exists(token_path):
        raise FileNotFoundError(f"Token file not found at {token_path}. Run the OAuth setup script first.")
    
    # Load credentials from token file (JSON format)
    with open(token_path, 'r') as token:
        token_data = json.load(token)
    
    creds = Credentials.from_authorized_user_info(token_data)
    
    # Refresh token if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Calendar credentials refreshed successfully")
            
            # Save refreshed token back to file
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
                
        except Exception as e:
            logger.error(f"Failed to refresh Calendar credentials: {e}")
            raise
    
    # Build Calendar service
    try:
        service = build('calendar', 'v3', credentials=creds)
        logger.info("Calendar service initialized successfully")
        return service
    except Exception as e:
        logger.error(f"Failed to build Calendar service: {e}")
        raise


def get_calendar_id():
    """
    Get the calendar ID from configuration. 
    This function enforces that only the explicitly configured shared calendar is used.
    
    Returns:
        str: Calendar ID to use for operations
        
    Raises:
        ValueError: If no calendar is configured or if trying to use primary calendar
    """
    config = get_config()
    calendar_config = config.get('calendar', {})
    
    # First check if calendar_id is explicitly configured
    if 'calendar_id' in calendar_config:
        calendar_id = calendar_config['calendar_id']
        
        # Prevent using primary calendar unless explicitly intended
        if calendar_id == 'primary':
            logger.warning("calendar_id is set to 'primary' - this will use your personal calendar!")
            logger.warning("For shared calendar operations, use 'calendar_cid' or specify the actual calendar ID")
            logger.warning("If you really want to use your primary calendar, set 'allow_primary_calendar: true' in config")
            
            if not calendar_config.get('allow_primary_calendar', False):
                raise ValueError("Using primary calendar is not allowed. Configure 'calendar_cid' or 'calendar_id' with a shared calendar ID, or set 'allow_primary_calendar: true' to override.")
        
        logger.info(f"Using configured calendar ID: {calendar_id}")
        return calendar_id
    
    # Check if there's a calendar_cid (base64 encoded calendar ID from share URL)
    if 'calendar_cid' in calendar_config:
        try:
            # Decode base64 calendar ID
            calendar_id = base64.b64decode(calendar_config['calendar_cid']).decode('utf-8')
            logger.info(f"Using decoded calendar ID from cid: {calendar_id}")
            
            # Validate that the decoded calendar ID looks reasonable (contains @)
            if '@' not in calendar_id and calendar_id != 'primary':
                logger.warning(f"Decoded calendar ID '{calendar_id}' doesn't look like an email address. Double-check your calendar_cid.")
            
            return calendar_id
        except Exception as e:
            logger.error(f"Failed to decode calendar_cid: {e}")
            raise ValueError(f"Invalid calendar_cid in configuration: {e}")
    
    # No calendar configured - require explicit configuration
    raise ValueError(
        "No calendar configured! Please add either:\n"
        "  - 'calendar_cid': '<base64_encoded_calendar_id>' (from Google Calendar share URL)\n"
        "  - 'calendar_id': '<actual_calendar_id>'\n"
        "to your calendar configuration. Use the /calendar/calendars/discover endpoint to find available calendars."
    )


def discover_shared_calendars():
    """
    Discover all calendars the user has access to, useful for finding shared calendars.
    
    Returns:
        List[Dict]: List of calendar information
    """
    try:
        service = get_calendar_service()
        
        # Get the user's calendar list
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        logger.info(f"Discovered {len(calendars)} calendars")
        
        # Log calendar details for debugging
        for calendar in calendars:
            logger.info(f"Calendar: {calendar.get('summary')} (ID: {calendar.get('id')}, "
                       f"Access: {calendar.get('accessRole')}, Primary: {calendar.get('primary', False)})")
        
        return calendars
        
    except Exception as e:
        logger.error(f"Failed to discover calendars: {e}")
        return []


def validate_calendar_access():
    """
    Validate that the configured calendar exists and is accessible.
    
    Returns:
        Dict: Calendar information if accessible
        
    Raises:
        ValueError: If calendar is not accessible or doesn't exist
    """
    try:
        service = get_calendar_service()
        calendar_id = get_calendar_id()
        
        # Try to get calendar metadata
        try:
            calendar_info = service.calendars().get(calendarId=calendar_id).execute()
            logger.info(f"Successfully validated calendar access: {calendar_info.get('summary')} ({calendar_id})")
            return calendar_info
            
        except Exception as calendar_error:
            # If direct calendar access fails, check if it's in the calendar list
            logger.warning(f"Direct calendar access failed: {calendar_error}")
            logger.info("Checking calendar list for access...")
            
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            for calendar in calendars:
                if calendar.get('id') == calendar_id:
                    logger.info(f"Found calendar in calendar list: {calendar.get('summary')} "
                              f"(Access: {calendar.get('accessRole')})")
                    return calendar
            
            # Calendar not found in calendar list
            raise ValueError(
                f"Calendar '{calendar_id}' not found or not accessible. "
                f"Available calendars: {[c.get('id') for c in calendars]}"
            )
        
    except Exception as e:
        logger.error(f"Calendar validation failed: {e}")
        raise


def get_calendar_summary():
    """
    Get a human-readable summary of the configured calendar.
    
    Returns:
        str: Calendar summary/name
    """
    try:
        calendar_info = validate_calendar_access()
        return calendar_info.get('summary', 'Unknown Calendar')
    except Exception as e:
        logger.warning(f"Could not get calendar summary: {e}")
        return f"Calendar ({get_calendar_id()})"
