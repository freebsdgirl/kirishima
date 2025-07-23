"""
Gmail API Routes for FastAPI
This module defines the API endpoints for interacting with Gmail via Google's API.
It provides endpoints for sending, replying, forwarding, and saving emails as drafts,
as well as searching, retrieving, and monitoring emails.
Endpoints:
    - POST /send: Send a new email.
    - POST /reply: Reply to an existing email thread.
    - POST /forward: Forward an email to specified recipients.
    - POST /draft: Save an email as a draft.
    - GET /drafts: Retrieve a list of draft emails.
    - POST /search: Search emails using Gmail query syntax.
    - GET /unread: Retrieve unread emails.
    - GET /recent: Retrieve recent emails.
    - POST /search/sender: Search emails by sender.
    - POST /search/subject: Search emails by subject.
    - GET /email/{email_id}: Retrieve a specific email by its ID.
    - POST /monitor/start: Start email monitoring in the background.
    - POST /monitor/stop: Stop email monitoring.
    - GET /monitor/status: Get the current status of email monitoring.
All endpoints handle exceptions and return appropriate HTTP error responses.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, status

from shared.models.googleapi import (
    SendEmailRequest,
    ReplyEmailRequest,
    ForwardEmailRequest,
    SaveDraftRequest,
    SearchEmailRequest,
    EmailSearchByRequest,
    EmailResponse
)

from app.gmail.auth import get_gmail_service
from app.gmail.send import send_email, reply_to_email, forward_email, save_draft, get_drafts
from app.gmail.search import search_emails, get_unread_emails, get_recent_emails, get_emails_by_sender, get_emails_by_subject, get_email_by_id
from app.gmail.monitor import start_email_monitoring, stop_email_monitoring, get_monitor_status

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

router = APIRouter()


# Email sending endpoints
@router.post("/send", response_model=EmailResponse)
async def send_email_endpoint(request: SendEmailRequest):
    """Send a new email."""
    try:
        service = get_gmail_service()
        result = send_email(service=service, request=request)
        return result
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/reply", response_model=EmailResponse)
async def reply_to_email_endpoint(request: ReplyEmailRequest):
    """Reply to an email thread."""
    try:
        service = get_gmail_service()
        result = reply_to_email(service=service, request=request)
        return result
    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/forward", response_model=EmailResponse)
async def forward_email_endpoint(request: ForwardEmailRequest):
    """Forward an email to recipients."""
    try:
        service = get_gmail_service()
        result = forward_email(service=service, request=request)
        return result
    except Exception as e:
        logger.error(f"Error forwarding email: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/draft", response_model=EmailResponse)
async def save_draft_endpoint(request: SaveDraftRequest):
    """Save an email as a draft for later review and sending."""
    try:
        service = get_gmail_service()
        result = save_draft(service=service, request=request)
        return result
    except Exception as e:
        logger.error(f"Error saving draft: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/drafts", response_model=EmailResponse)
async def get_drafts_endpoint(max_results: int = 10):
    """Get list of draft emails for review."""
    try:
        service = get_gmail_service()
        result = get_drafts(service=service, max_results=max_results)
        return result
    except Exception as e:
        logger.error(f"Error getting drafts: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Email search endpoints
@router.post("/search", response_model=EmailResponse)
async def search_emails_endpoint(request: SearchEmailRequest):
    """Search emails using Gmail query syntax."""
    try:
        service = get_gmail_service()
        result = search_emails(service=service, request=request)
        return result
    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/unread", response_model=EmailResponse)
async def get_unread_emails_endpoint(max_results: int = 10):
    """Get unread emails."""
    try:
        service = get_gmail_service()
        result = get_unread_emails(service=service, max_results=max_results)
        return result
    except Exception as e:
        logger.error(f"Error getting unread emails: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/recent", response_model=EmailResponse)
async def get_recent_emails_endpoint(max_results: int = 10):
    """Get recent emails."""
    try:
        service = get_gmail_service()
        result = get_recent_emails(service=service, max_results=max_results)
        return result
    except Exception as e:
        logger.error(f"Error getting recent emails: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/search/sender", response_model=EmailResponse)
async def search_by_sender_endpoint(request: EmailSearchByRequest):
    """Search emails by sender."""
    try:
        service = get_gmail_service()
        result = get_emails_by_sender(service=service, request=request)
        return result
    except Exception as e:
        logger.error(f"Error searching emails by sender: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/search/subject", response_model=EmailResponse)
async def search_by_subject_endpoint(request: EmailSearchByRequest):
    """Search emails by subject."""
    try:
        service = get_gmail_service()
        result = get_emails_by_subject(service=service, request=request)
        return result
    except Exception as e:
        logger.error(f"Error searching emails by subject: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/email/{email_id}", response_model=EmailResponse)
async def get_email_by_id_endpoint(email_id: str):
    """Get a specific email by ID."""
    try:
        service = get_gmail_service()
        result = get_email_by_id(service=service, email_id=email_id)
        return result
    except Exception as e:
        logger.error(f"Error getting email {email_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Email monitoring endpoints
@router.post("/monitor/start", response_model=EmailResponse)
async def start_monitoring_endpoint(background_tasks: BackgroundTasks):
    """Start email monitoring."""
    try:
        background_tasks.add_task(start_email_monitoring)
        
        return EmailResponse(
            success=True,
            message="Email monitoring started"
        )
        
    except Exception as e:
        logger.error(f"Error starting email monitoring: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/monitor/stop", response_model=EmailResponse)
async def stop_monitoring_endpoint():
    """Stop email monitoring."""
    try:
        stop_email_monitoring()
        
        return EmailResponse(
            success=True,
            message="Email monitoring stopped"
        )
        
    except Exception as e:
        logger.error(f"Error stopping email monitoring: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/monitor/status", response_model=EmailResponse)
async def get_monitoring_status_endpoint():
    """Get email monitoring status."""
    try:
        status = get_monitor_status()
        
        return EmailResponse(
            success=True,
            message="Monitor status retrieved",
            data={"status": status}
        )
        
    except Exception as e:
        logger.error(f"Error getting monitor status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
