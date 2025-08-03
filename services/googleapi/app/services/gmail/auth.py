"""
This module provides authentication utilities for accessing the Gmail API using OAuth2 credentials.
Functions:
    get_config():
        Loads configuration settings from a JSON file.
    get_gmail_service():
        Loads OAuth2 credentials from a token file, refreshes them if expired, and returns an authenticated Gmail API service instance.
    get_user_profile(service):
        Retrieves the authenticated user's Gmail profile information using the provided Gmail service.
Logging:
    Uses a shared logger for error and status reporting.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.gmail.util import get_config

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

import os
import json


def get_gmail_service():
    """
    Load OAuth2 credentials and return an authenticated Gmail service.
    
    Returns:
        googleapiclient.discovery.Resource: Authenticated Gmail service
        
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
            logger.info("Refreshing expired Gmail credentials")
            creds.refresh(Request())
            # Save refreshed token
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            logger.info("Gmail credentials refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh Gmail credentials: {e}")
            raise Exception(f"Token refresh failed. Re-run OAuth setup: {e}")
    
    if not creds.valid:
        raise Exception("Invalid credentials. Re-run the OAuth setup script.")
    
    # Build and return Gmail service
    service = build('gmail', 'v1', credentials=creds)
    return service


def get_user_profile(service):
    """
    Get the authenticated user's Gmail profile.
    
    Args:
        service: Authenticated Gmail service
        
    Returns:
        dict: User profile information
    """
    try:
        profile = service.users().getProfile(userId='me').execute()
        return profile
    except Exception as e:
        raise Exception(f"Failed to get user profile: {str(e)}")
