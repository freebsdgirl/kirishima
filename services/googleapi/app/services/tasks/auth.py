"""
This module provides authentication and access validation utilities for the Google Tasks API,
using OAuth2 credentials and a comprehensive set of Google API scopes to ensure compatibility
with other Google services (Mail, Contacts, Calendar, User Info, Tasks, OpenID).
Functions:
    get_tasks_service():
        Authenticates and returns a Google Tasks service instance using OAuth2 credentials.
        Handles credential loading, refreshing, and OAuth flow as needed.
        Returns a googleapiclient.discovery.Resource for interacting with the Google Tasks API.
    validate_tasks_access():
        Validates that Google Tasks API access is working by attempting to list task lists.
        Returns a dictionary indicating success status, a message, and the number of task lists found.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

# Google API scopes - using comprehensive set to match main OAuth setup
SCOPES = [
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/contacts',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/tasks',
    'openid'
]

def get_tasks_service():
    """
    Authenticate and return a Google Tasks service instance.
    Uses comprehensive OAuth scopes to maintain token compatibility with other Google services.
    
    Returns:
        googleapiclient.discovery.Resource: Google Tasks service instance
        
    Raises:
        Exception: If authentication fails
    """
    try:
        creds = None
        
        # Load existing credentials
        token_path = '/app/config/token.json'
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired Google Tasks credentials")
                creds.refresh(Request())
            else:
                logger.info("Starting Google OAuth flow with comprehensive scopes")
                credentials_path = '/app/config/credentials.json'
                if not os.path.exists(credentials_path):
                    raise Exception("credentials.json not found. Please set up Google API credentials.")
                
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Build and return the service
        service = build('tasks', 'v1', credentials=creds)
        logger.info("Google Tasks service authenticated successfully (with comprehensive scopes)")
        return service
        
    except Exception as e:
        logger.error(f"Failed to authenticate Google Tasks service: {e}")
        raise


def validate_tasks_access():
    """
    Validate that Google Tasks API access is working.
    Note: Uses comprehensive OAuth scopes for compatibility with other Google services.
    
    Returns:
        dict: Validation result with success status and message
    """
    try:
        service = get_tasks_service()
        
        # Try to list task lists to validate access
        result = service.tasklists().list().execute()
        task_lists = result.get('items', [])
        
        logger.info(f"Google Tasks validation successful. Found {len(task_lists)} task lists.")
        
        return {
            "success": True,
            "message": f"Google Tasks access validated. Found {len(task_lists)} task lists.",
            "task_lists_count": len(task_lists)
        }
        
    except Exception as e:
        logger.error(f"Google Tasks validation failed: {e}")
        return {
            "success": False,
            "message": f"Google Tasks validation failed: {str(e)}",
            "task_lists_count": 0
        }
