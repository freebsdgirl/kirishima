"""
Authentication utilities for Google Contacts API using OAuth2 credentials.

Functions:
    get_people_service():
        Loads OAuth2 credentials from a token file, refreshes them if expired, 
        and returns an authenticated People API service instance.
        
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


def get_people_service():
    """
    Load OAuth2 credentials and return an authenticated People API service.
    
    Returns:
        googleapiclient.discovery.Resource: Authenticated People API service
        
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
            logger.info("Refreshing expired Contacts credentials")
            creds.refresh(Request())
            # Save refreshed token
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            logger.info("Contacts credentials refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh Contacts credentials: {e}")
            raise Exception(f"Token refresh failed. Re-run OAuth setup: {e}")
    
    if not creds.valid:
        raise Exception("Invalid credentials. Re-run the OAuth setup script.")
    
    # Build and return People API service
    service = build('people', 'v1', credentials=creds)
    return service
