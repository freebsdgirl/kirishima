"""
This module provides Gmail email sending, forwarding, replying, draft saving, and draft retrieval functionalities using the Gmail API and shared data models.
Functions:
    - forward_email(service, request: ForwardEmailRequest) -> EmailResponse:
        Forwards the latest message in a Gmail thread to a new recipient, optionally with a preface body, and returns an EmailResponse indicating success or failure.
    - create_message(request: SendEmailRequest) -> dict:
        Constructs a MIME email message (with optional attachments) from a SendEmailRequest model and returns it as a base64-encoded dictionary suitable for the Gmail API.
    - send_email(service, request: SendEmailRequest) -> EmailResponse:
        Sends an email using the Gmail API based on the provided SendEmailRequest model and returns an EmailResponse with the result.
    - reply_to_email(service, request: ReplyEmailRequest) -> EmailResponse:
        Replies to the latest message in a Gmail thread, maintaining proper threading headers, and returns an EmailResponse indicating the result.
    - save_draft(service, request: SaveDraftRequest) -> EmailResponse:
        Saves an email as a draft in Gmail using the provided SaveDraftRequest model and returns an EmailResponse with draft details.
    - get_drafts(service, max_results: int = 10) -> EmailResponse:
        Retrieves a list of draft emails from Gmail, up to the specified maximum number, and returns an EmailResponse containing draft metadata.
Dependencies:
    - shared.models.googleapi: Data models for email requests and responses.
    - shared.log_config: Logger configuration.
    - email, base64, os: Standard libraries for email construction and encoding.
"""
from shared.models.googleapi import (
    ForwardEmailRequest,
    SendEmailRequest,
    SaveDraftRequest,
    EmailResponse
)

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from shared.models.googleapi import ReplyEmailRequest

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import base64
import os


def forward_email(service, request: ForwardEmailRequest) -> EmailResponse:
    """
    Forward an email in a thread to a new recipient, with a preface body.
    Args:
        service: Authenticated Gmail service
        request: ForwardEmailRequest model
    Returns:
        EmailResponse model
    """
    try:
        # Get the original message from the thread
        thread = service.users().threads().get(userId='me', id=request.thread_id).execute()
        last_message = thread['messages'][-1]
        headers = last_message['payload']['headers']
        subject = None
        from_addr = None
        date = None
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
            if header['name'].lower() == 'from':
                from_addr = header['value']
            if header['name'].lower() == 'date':
                date = header['value']
        if subject and not subject.lower().startswith('fwd:'):
            subject = f"Fwd: {subject}"
        # Extract original body
        payload = last_message.get('payload', {})
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    import base64
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        elif payload.get('mimeType') == 'text/plain':
            import base64
            data = payload.get('body', {}).get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        # Compose forwarded content
        forwarded_content = f"{request.body}\n\n--- Forwarded message ---\nFrom: {from_addr}\nDate: {date}\nSubject: {subject}\n\n{body}"
        # Build SendEmailRequest
        send_request = SendEmailRequest(
            to=request.to,
            subject=subject,
            body=forwarded_content
        )
        message = create_message(send_request)
        result = service.users().messages().send(userId='me', body=message).execute()
        return EmailResponse(
            success=True,
            message="Email forwarded successfully",
            data={
                "message_id": result['id'],
                "thread_id": result['threadId'],
                "status": "forwarded"
            }
        )
    except Exception as e:
        return EmailResponse(success=False, message=f"Failed to forward email: {str(e)}", data=None)


"""
Gmail send functionality.
"""


def create_message(request: SendEmailRequest):
    """
    Create a message for an email using a shared model.
    Args:
        request: SendEmailRequest model
    Returns:
        dict: Message ready to be sent
    """
    message = MIMEMultipart()
    message['to'] = request.to
    message['subject'] = request.subject
    # Optionally set 'from' if present in model (not currently in SendEmailRequest)
    if hasattr(request, 'from_email') and request.from_email:
        message['from'] = request.from_email
    if request.cc:
        message['cc'] = request.cc
    if request.bcc:
        message['bcc'] = request.bcc
    # Add body
    message.attach(MIMEText(request.body, 'plain'))
    # Add attachments if provided
    if request.attachments:
        for file_path in request.attachments:
            if os.path.isfile(file_path):
                with open(file_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(file_path)}'
                )
                message.attach(part)
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw_message}


def send_email(service, request: SendEmailRequest) -> EmailResponse:
    """
    Send an email using Gmail API and shared models.
    Args:
        service: Authenticated Gmail service
        request: SendEmailRequest model
    Returns:
        EmailResponse model
    """
    try:
        message = create_message(request)
        result = service.users().messages().send(userId='me', body=message).execute()
        return EmailResponse(
            success=True,
            message="Email sent successfully",
            data={
                "message_id": result['id'],
                "thread_id": result['threadId'],
                "status": "sent"
            }
        )
    except Exception as e:
        return EmailResponse(success=False, message=f"Failed to send email: {str(e)}", data=None)


def reply_to_email(service, request: ReplyEmailRequest) -> EmailResponse:
    """
    Reply to an email thread using shared models.
    Args:
        service: Authenticated Gmail service
        request: ReplyEmailRequest model
    Returns:
        EmailResponse model
    """
    try:
        thread = service.users().threads().get(userId='me', id=request.thread_id).execute()
        last_message = thread['messages'][-1]
        headers = last_message['payload']['headers']
        subject = None
        to = None
        message_id = None
        references = None
        
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
            if header['name'].lower() == 'from':
                to = header['value']
            if header['name'].lower() == 'message-id':
                message_id = header['value']
            if header['name'].lower() == 'references':
                references = header['value']
        
        if subject and not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"
        
        # Create reply message with proper threading headers
        message = MIMEMultipart()
        message['to'] = to
        message['subject'] = subject or "Re:"
        
        # Set threading headers to maintain conversation
        if message_id:
            message['In-Reply-To'] = message_id
            if references:
                message['References'] = f"{references} {message_id}"
            else:
                message['References'] = message_id
        
        # Add body
        message.attach(MIMEText(request.body, 'plain'))
        
        # Add attachments if provided
        if request.attachments:
            for file_path in request.attachments:
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(file_path)}'
                    )
                    message.attach(part)
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        message_payload = {'raw': raw_message, 'threadId': request.thread_id}
        
        result = service.users().messages().send(userId='me', body=message_payload).execute()
        return EmailResponse(
            success=True,
            message="Reply sent successfully",
            data={
                "message_id": result['id'],
                "thread_id": result['threadId'],
                "status": "sent"
            }
        )
    except Exception as e:
        return EmailResponse(success=False, message=f"Failed to send reply: {str(e)}", data=None)


def save_draft(service, request: SaveDraftRequest) -> EmailResponse:
    """
    Save an email as a draft for later review and sending.
    
    Args:
        service: Authenticated Gmail service
        request: SaveDraftRequest model
        
    Returns:
        EmailResponse model
    """
    try:
        # Create the email message
        message = MIMEText(request.body, 'plain')
        message['To'] = request.to
        message['Subject'] = request.subject
        
        if request.from_email:
            message['From'] = request.from_email
        
        if request.cc:
            message['Cc'] = request.cc
            
        if request.bcc:
            message['Bcc'] = request.bcc

        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Create draft
        draft_body = {
            'message': {
                'raw': raw_message
            }
        }

        draft = service.users().drafts().create(userId='me', body=draft_body).execute()
        
        logger.info(f"Draft saved successfully: {draft['id']} with subject: {request.subject}")
        
        return EmailResponse(
            success=True,
            message="Draft saved successfully",
            data={
                "draft_id": draft['id'],
                "subject": request.subject,
                "to": request.to,
                "cc": request.cc,
                "bcc": request.bcc
            }
        )
    except Exception as e:
        logger.error(f"Failed to save draft: {str(e)}")
        return EmailResponse(success=False, message=f"Failed to save draft: {str(e)}", data=None)


def get_drafts(service, max_results: int = 10) -> EmailResponse:
    """
    Get a list of draft emails.
    
    Args:
        service: Authenticated Gmail service
        max_results: Maximum number of drafts to return
        
    Returns:
        EmailResponse model with drafts data
    """
    try:
        # Get list of drafts
        drafts_result = service.users().drafts().list(userId='me', maxResults=max_results).execute()
        drafts = drafts_result.get('drafts', [])
        
        draft_list = []
        for draft in drafts:
            # Get full draft details
            draft_detail = service.users().drafts().get(userId='me', id=draft['id']).execute()
            message = draft_detail['message']
            
            # Extract headers
            headers = {h['name']: h['value'] for h in message['payload']['headers']}
            
            draft_info = {
                'draft_id': draft['id'],
                'message_id': message['id'],
                'subject': headers.get('Subject', 'No Subject'),
                'to': headers.get('To', ''),
                'cc': headers.get('Cc', ''),
                'bcc': headers.get('Bcc', ''),
                'date': headers.get('Date', ''),
                'snippet': message.get('snippet', '')
            }
            draft_list.append(draft_info)
        
        logger.info(f"Retrieved {len(draft_list)} drafts")
        
        return EmailResponse(
            success=True,
            message=f"Retrieved {len(draft_list)} drafts",
            data={"drafts": draft_list}
        )
    except Exception as e:
        logger.error(f"Failed to get drafts: {str(e)}")
        return EmailResponse(success=False, message=f"Failed to get drafts: {str(e)}", data=None)
