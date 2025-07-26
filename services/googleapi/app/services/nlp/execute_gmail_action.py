"""
This module provides the `_execute_gmail_action` asynchronous function to handle various Gmail-related actions such as sending emails (as drafts), searching emails, retrieving emails by ID, and forwarding emails. It integrates with Gmail services and utilities for contact resolution, email formatting, and content cleaning.
Functions:
    _execute_gmail_action(action: str, params: Dict[str, Any], slim: bool = True, readable: bool = False) -> Dict[str, Any]:
        Executes a specified Gmail action based on the provided action string and parameters.
        Supported actions:
            - "send_email": Resolves recipient, saves the email as a draft, and returns a response mimicking a sent email.
            - "search_emails": Searches emails using a query, returning results in slim or readable format if specified.
            - "get_email_by_id": Retrieves and cleans an email by its ID, optionally returning slimmed data for LLM processing.
            - "forward_email": Resolves recipient and forwards an email in a specified thread.
        Raises:
            HTTPException: If an unknown action is provided.
"""
from typing import Dict, Any
from fastapi import HTTPException
from shared.models.googleapi import (
    ForwardEmailRequest,
    SaveDraftRequest,
    SearchEmailRequest
)

from app.services.nlp.resolve_contact_email import resolve_contact_email
from app.services.gmail.send import forward_email, save_draft
from app.services.gmail.search import search_emails, get_email_by_id
from app.services.gmail.email_cleaner import clean_email_for_brain, get_email_summary_stats
from app.services.text_formatter import format_emails_readable
from app.services.gmail.auth import get_gmail_service

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")


async def _execute_gmail_action(action: str, params: Dict[str, Any], slim: bool = True, readable: bool = False) -> Dict[str, Any]:
    """Execute Gmail-specific actions."""
    if action == "send_email":
        # Resolve contact name to email if needed
        to_email = await resolve_contact_email(params["to"])
        
        # Create a draft request instead of send request
        draft_request = SaveDraftRequest(
            to=to_email,
            subject=params["subject"],
            body=params["body"],
            cc=params.get("cc"),
            bcc=params.get("bcc")
        )
        
        service = get_gmail_service()
        # Save as draft instead of sending
        result = save_draft(service=service, request=draft_request)
        
        # Return response that looks like email was sent
        return {
            "email_id": result.data.get("draft_id") if result.data else None,  # Use draft_id as email_id
            "message": "Email sent successfully",  # Maintain appearance of sending
            "success": result.success,
            "resolved_to": to_email,
            "status": "sent",  # Maintain appearance of being sent
            "_debug_note": "Actually saved as draft"  # Optional debug info
        }
        
    elif action == "search_emails":
        search_request = SearchEmailRequest(query=params["query"])
        service = get_gmail_service()
        result = search_emails(service=service, request=search_request)
        
        # Extract emails from the data field
        emails_data = result.data.get("emails", []) if result.data else []
        
        if readable:
            # Return human-readable format
            readable_text = format_emails_readable(emails_data)
            return {
                "result": readable_text,
                "count": len(emails_data),
                "success": result.success,
                "message": result.message
            }
        elif slim and emails_data:
            # Return only essential fields for each email to reduce token usage
            slim_emails = []
            for email in emails_data:
                slim_email = {
                    "id": email.get("id"),
                    "subject": email.get("subject"),
                    "from": email.get("from"),
                    "date": email.get("date"),
                    "snippet": email.get("snippet"),
                    "is_reply": email.get("is_reply", False)
                }
                slim_emails.append(slim_email)
            
            return {
                "emails": slim_emails,
                "count": len(slim_emails),
                "success": result.success,
                "message": result.message
            }
        else:
            return {
                "emails": emails_data,
                "count": len(emails_data),
                "success": result.success,
                "message": result.message
            }
        
    elif action == "get_email_by_id":
        service = get_gmail_service()
        result = get_email_by_id(
            service=service, 
            email_id=params["email_id"],
            format=params.get("format", "full")
        )
        
        # Extract email data from the response
        email_data = result.data.get("email") if result.data else None
        
        # Clean the email content for better processing
        if email_data:
            # Include thread context for replies (pass Gmail service)
            cleaned_email = clean_email_for_brain(email_data, gmail_service=service)
            stats = get_email_summary_stats(cleaned_email)
            
            logger.info(f"Retrieved and cleaned email {email_data.get('id', 'unknown')}: "
                       f"{stats['word_count']} words, is_reply={stats['is_reply']}, "
                       f"has_thread_context={cleaned_email.get('has_thread_context', False)}")
            
            if slim:
                # Return only essential data for LLM processing
                return {
                    "email": {
                        "id": cleaned_email.get("id"),
                        "subject": cleaned_email.get("subject"),
                        "from": cleaned_email.get("from"),
                        "to": cleaned_email.get("to"), 
                        "date": cleaned_email.get("date"),
                        "body_cleaned": cleaned_email.get("body_cleaned"),
                        "is_reply": cleaned_email.get("is_reply", False),
                        "thread_summary": cleaned_email.get("thread_summary"),
                        "has_thread_context": cleaned_email.get("has_thread_context", False),
                        "word_count": stats["word_count"]
                    },
                    "success": result.success,
                    "message": result.message
                }
            else:
                # Return both cleaned and original data
                return {
                    "email": cleaned_email,
                    "email_raw": email_data,  # Keep original for reference
                    "stats": stats,
                    "success": result.success,
                    "message": result.message
                }
        
        return {
            "email": email_data,
            "success": result.success,
            "message": result.message
        }
        
    elif action == "forward_email":
        # Resolve contact name to email if needed
        to_email = await resolve_contact_email(params["to"])
        
        forward_request = ForwardEmailRequest(
            thread_id=params["thread_id"],
            body=params["body"],
            to=to_email
        )
        
        service = get_gmail_service()
        result = forward_email(service=service, request=forward_request)
        return {
            "email_id": result.data.get("message_id") if result.data else None,
            "message": result.message,
            "success": result.success,
            "resolved_to": to_email
        }
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown Gmail action: {action}")