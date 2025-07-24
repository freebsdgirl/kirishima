"""
Google Tasks API authentication module.
Provides functions to authenticate and get a Google Tasks service instance.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import json

# Google Tasks API scope
SCOPES = ['https://www.googleapis.com/auth/tasks']

def get_tasks_service():
    """
    Authenticate and return a Google Tasks service instance.
    
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
                logger.info("Starting Google Tasks OAuth flow")
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
        logger.info("Google Tasks service authenticated successfully")
        return service
        
    except Exception as e:
        logger.error(f"Failed to authenticate Google Tasks service: {e}")
        raise


def validate_tasks_access():
    """
    Validate that Google Tasks API access is working.
    
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
