"""
This module provides services for searching and retrieving emails using the Gmail API.
It defines functions to search emails by various criteria (query, unread, recent, sender, subject),
retrieve a specific email by its ID, and extract body content from email payloads.
All functions utilize shared models for request and response handling.
Functions:
    - search_emails: Search for emails using Gmail's search syntax.
    - get_unread_emails: Retrieve unread emails from the inbox.
    - get_recent_emails: Retrieve recent emails from the inbox.
    - get_emails_by_sender: Retrieve emails sent by a specific sender.
    - get_emails_by_subject: Retrieve emails with a specific subject.
    - get_email_by_id: Retrieve a specific email by its ID.
    - extract_body_content: Extract text and HTML body content from an email payload.
"""
from shared.models.googleapi import (
    SearchEmailRequest,
    EmailSearchByRequest,
    ApiResponse
)

from googleapiclient.discovery import Resource

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from typing import Dict, Any


def search_emails(service, request: SearchEmailRequest) -> ApiResponse:
    """
    Search for emails using Gmail's search syntax and shared models.
    Args:
        service: Authenticated Gmail service
        request: SearchEmailRequest model
    Returns:
        ApiResponse model
    """
    try:
        results = service.users().messages().list(
            userId='me',
            q=request.query,
            maxResults=request.max_results,
            includeSpamTrash=False
        ).execute()
        messages = results.get('messages', [])
        if not messages:
            return ApiResponse(success=True, message="No emails found", data={"emails": []})
        email_list = []
        for message in messages:
            msg = service.users().messages().get(
                userId='me', 
                id=message['id'],
                format='metadata',
                metadataHeaders=['From', 'To', 'Subject', 'Date']
            ).execute()
            headers = {}
            if 'payload' in msg and 'headers' in msg['payload']:
                for header in msg['payload']['headers']:
                    headers[header['name'].lower()] = header['value']
            email_info = {
                'id': msg['id'],
                'thread_id': msg['threadId'],
                'snippet': msg.get('snippet', ''),
                'from': headers.get('from', ''),
                'to': headers.get('to', ''),
                'subject': headers.get('subject', ''),
                'date': headers.get('date', ''),
                'labels': msg.get('labelIds', [])
            }
            email_list.append(email_info)
        return ApiResponse(success=True, message=f"Found {len(email_list)} emails", data={"emails": email_list})
    except Exception as e:
        return ApiResponse(success=False, message=f"Failed to search emails: {str(e)}", data=None)


def get_unread_emails(service, max_results: int = 10) -> ApiResponse:
    """
    Get unread emails from inbox using shared models.
    """
    req = SearchEmailRequest(query='is:unread in:inbox', max_results=max_results)
    return search_emails(service, req)


def get_recent_emails(service, max_results: int = 10) -> ApiResponse:
    """
    Get recent emails from inbox using shared models.
    """
    req = SearchEmailRequest(query='in:inbox', max_results=max_results)
    return search_emails(service, req)


def get_emails_by_sender(service, request: EmailSearchByRequest) -> ApiResponse:
    """
    Get emails by sender using shared models.
    """
    req = SearchEmailRequest(query=f'from:{request.value}', max_results=request.max_results)
    return search_emails(service, req)


def get_emails_by_subject(service, request: EmailSearchByRequest) -> ApiResponse:
    """
    Get emails by subject using shared models.
    """
    req = SearchEmailRequest(query=f'subject:"{request.value}"', max_results=request.max_results)
    return search_emails(service, req)


def get_email_by_id(service: Resource, email_id: str, format: str = "full") -> ApiResponse:
    """
    Retrieve a specific email by its ID using shared models.
    """
    try:
        logger.info(f"Retrieving email with ID: {email_id}")
        message = service.users().messages().get(
            userId='me',
            id=email_id,
            format=format
        ).execute()
        headers = {h['name']: h['value'] for h in message.get('payload', {}).get('headers', [])}
        result = {
            'id': message['id'],
            'threadId': message['threadId'],
            'labelIds': message.get('labelIds', []),
            'snippet': message.get('snippet', ''),
            'historyId': message.get('historyId'),
            'internalDate': message.get('internalDate'),
            'subject': headers.get('Subject', ''),
            'from': headers.get('From', ''),
            'to': headers.get('To', ''),
            'cc': headers.get('Cc', ''),
            'bcc': headers.get('Bcc', ''),
            'date': headers.get('Date', ''),
            'message-id': headers.get('Message-ID', ''),
            'headers': headers,
            'payload': message.get('payload', {})
        }
        body = extract_body_content(message.get('payload', {}))
        result['body'] = body
        return ApiResponse(success=True, message="Email retrieved successfully", data={"email": result})
    except Exception as e:
        logger.error(f"Error retrieving email {email_id}: {e}")
        return ApiResponse(success=False, message=f"Error retrieving email {email_id}: {e}", data=None)


def extract_body_content(payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract text and HTML body content from email payload.
    
    Args:
        payload: Email payload from Gmail API
    
    Returns:
        Dictionary with 'text' and 'html' content
    """
    body = {'text': '', 'html': ''}


    def extract_from_part(part):
        mime_type = part.get('mimeType', '')
        if mime_type == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                import base64
                body['text'] = base64.urlsafe_b64decode(data).decode('utf-8')
        elif mime_type == 'text/html':
            data = part.get('body', {}).get('data', '')
            if data:
                import base64
                body['html'] = base64.urlsafe_b64decode(data).decode('utf-8')
        elif 'parts' in part:
            for subpart in part['parts']:
                extract_from_part(subpart)
    
    extract_from_part(payload)
    return body
