"""
Script to perform Google OAuth2 flow and save token.json in ~/.kirishima/

Usage:
    python scripts/google_oauth_setup.py

Requirements:
    - google-auth-oauthlib
    - google-auth
    - google-api-python-client

This script will prompt you to authenticate in your browser and save the token file for use by backend services.
"""
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Path to credentials.json (downloaded from Google Cloud Console)
CREDENTIALS_PATH = os.path.expanduser("~/.kirishima/credentials.json")
# Path to save token
TOKEN_PATH = os.path.expanduser("~/.kirishima/token.json")

# Scopes required for Gmail, Contacts, Calendar
SCOPES = [
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/contacts',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/tasks',
    'openid'
]

def main():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Missing credentials.json at {CREDENTIALS_PATH}. Download it from Google Cloud Console.")
        return

    creds = None
    # If token already exists, try to load it
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    # If no valid creds, start OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for future use
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    print(f"Token saved to {TOKEN_PATH}")

if __name__ == "__main__":
    main()
