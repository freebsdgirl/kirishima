"""
Email content cleaning and processing utilities for Gmail service.

This module provides utilities to clean and process email content before sending
to the brain service (LLM), including:
- Separating email replies from quoted content  
- Converting HTML emails to clean text
- Removing excessive formatting and whitespace
- Extracting relevant metadata

The goal is to reduce noise and provide cleaner, more focused content to the LLM
while preserving important context and structure.
"""

import re
import html
import httpx
import json
import os
from typing import Dict, Any, Optional, Tuple, List
from shared.log_config import get_logger
from shared.models.proxy import SingleTurnRequest
from shared.prompt_loader import load_prompt

logger = get_logger(f"googleapi.{__name__}")

THREAD_SUMMARY_WORD_LIMIT = 500
THREAD_SUMMARY_TARGET_WORDS = 400  # Target to stay under the limit

def clean_email_for_brain(email_data: Dict[str, Any], gmail_service=None) -> Dict[str, Any]:
    """
    Clean and process email data before sending to brain service.
    
    This function takes raw email data from Gmail API and returns a cleaned
    version optimized for LLM processing, with reduced noise and better structure.
    For reply emails, it also fetches and summarizes the thread context.
    
    Args:
        email_data: Raw email data from Gmail API containing headers and body
        gmail_service: Optional Gmail service instance for thread fetching
        
    Returns:
        Dict with cleaned email data and metadata for brain processing
    """
    # Extract basic email information
    subject = email_data.get('subject', 'No Subject')
    from_header = email_data.get('from', '')
    body_data = email_data.get('body', {})
    body_text = body_data.get('text', '')
    body_html = body_data.get('html', '')
    thread_id = email_data.get('threadId')
    
    # Use HTML content if text is not available
    if not body_text and body_html:
        body_text = convert_html_to_clean_text(body_html)
    
    # Clean the email body content
    cleaned_body = clean_email_body(body_text) if body_text else email_data.get('snippet', '')
    
    # Extract just the new content (remove quoted replies)
    new_content = extract_new_content(cleaned_body)
    
    # Determine if this is likely a reply
    is_reply = detect_if_reply(new_content, subject)
    
    # Initialize thread context
    thread_summary = None
    thread_context_available = False
    
    # If this is a reply and we have a Gmail service, get thread context
    if is_reply and thread_id and gmail_service:
        try:
            thread_summary = get_thread_summary(gmail_service, thread_id, exclude_current_email=email_data.get('id'))
            thread_context_available = bool(thread_summary)
            logger.info(f"Thread context {'found' if thread_context_available else 'not available'} for email {email_data.get('id', 'unknown')}")
        except Exception as e:
            logger.warning(f"Failed to get thread context for email {email_data.get('id', 'unknown')}: {e}")
    
    # Create cleaned email data
    cleaned_data = {
        'id': email_data.get('id'),
        'threadId': thread_id,
        'subject': subject,
        'from': from_header,
        'to': email_data.get('to', ''),
        'cc': email_data.get('cc', ''),
        'date': email_data.get('date', ''),
        'body_cleaned': new_content,
        'body_full': cleaned_body,  # Keep full content for reference
        'snippet': email_data.get('snippet', ''),
        'is_reply': is_reply,
        'word_count': len(new_content.split()) if new_content else 0,
        'thread_summary': thread_summary,
        'has_thread_context': thread_context_available
    }
    
    logger.debug(f"Cleaned email {email_data.get('id', 'unknown')}: "
                f"{cleaned_data['word_count']} words, is_reply={is_reply}, "
                f"has_thread_context={thread_context_available}")
    
    return cleaned_data


def get_thread_summary(gmail_service, thread_id: str, exclude_current_email: str = None) -> Optional[str]:
    """
    Get a summary of an email thread for context, excluding the current email.
    
    If the thread content is over THREAD_SUMMARY_WORD_LIMIT words, it will be
    summarized using the proxy service LLM.
    
    Args:
        gmail_service: Authenticated Gmail service
        thread_id: Gmail thread ID
        exclude_current_email: Email ID to exclude from the summary (usually the current email)
        
    Returns:
        str: Thread summary or None if unable to generate
    """
    try:
        # Fetch the thread
        thread_messages = get_thread_messages(gmail_service, thread_id, exclude_current_email)
        
        if not thread_messages:
            logger.debug(f"No thread messages found for thread {thread_id}")
            return None
        
        # Build thread content
        thread_content = build_thread_content(thread_messages)
        
        if not thread_content:
            logger.debug(f"No thread content extracted for thread {thread_id}")
            return None
        
        # Count words in thread content
        word_count = len(thread_content.split())
        logger.debug(f"Thread {thread_id} content: {word_count} words")
        
        # If thread is short enough, return as-is
        if word_count <= THREAD_SUMMARY_WORD_LIMIT:
            return thread_content
        
        # Otherwise, summarize it using the proxy service
        logger.info(f"Thread {thread_id} has {word_count} words, summarizing...")
        return summarize_thread_content(thread_content)
        
    except Exception as e:
        logger.error(f"Failed to get thread summary for {thread_id}: {e}")
        return None


def get_thread_messages(gmail_service, thread_id: str, exclude_email_id: str = None) -> List[Dict[str, Any]]:
    """
    Fetch all messages in a thread, excluding the specified email.
    
    Args:
        gmail_service: Authenticated Gmail service
        thread_id: Gmail thread ID
        exclude_email_id: Email ID to exclude from results
        
    Returns:
        List of message data dictionaries
    """
    try:
        thread = gmail_service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])
        
        # Exclude the current email if specified
        if exclude_email_id:
            messages = [msg for msg in messages if msg.get('id') != exclude_email_id]
        
        # Sort by internal date (chronological order)
        messages.sort(key=lambda x: int(x.get('internalDate', 0)))
        
        # Extract message data
        thread_messages = []
        for message in messages:
            # Get headers
            headers = {}
            if 'payload' in message and 'headers' in message['payload']:
                for header in message['payload']['headers']:
                    headers[header['name'].lower()] = header['value']
            
            # Extract body content
            body_data = extract_body_content_from_payload(message.get('payload', {}))
            
            thread_messages.append({
                'id': message.get('id'),
                'from': headers.get('from', ''),
                'to': headers.get('to', ''),
                'subject': headers.get('subject', ''),
                'date': headers.get('date', ''),
                'body_text': body_data.get('text', ''),
                'body_html': body_data.get('html', ''),
                'internal_date': message.get('internalDate')
            })
        
        return thread_messages
        
    except Exception as e:
        logger.error(f"Failed to fetch thread messages for {thread_id}: {e}")
        return []


def extract_body_content_from_payload(payload: Dict[str, Any]) -> Dict[str, str]:
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
                try:
                    body['text'] = base64.urlsafe_b64decode(data).decode('utf-8')
                except Exception as e:
                    logger.warning(f"Failed to decode text content: {e}")
        elif mime_type == 'text/html':
            data = part.get('body', {}).get('data', '')
            if data:
                import base64
                try:
                    body['html'] = base64.urlsafe_b64decode(data).decode('utf-8')
                except Exception as e:
                    logger.warning(f"Failed to decode HTML content: {e}")
        elif 'parts' in part:
            for subpart in part['parts']:
                extract_from_part(subpart)
    
    extract_from_part(payload)
    return body


def build_thread_content(thread_messages: List[Dict[str, Any]]) -> str:
    """
    Build a clean, chronological representation of thread messages.
    
    Args:
        thread_messages: List of message data from get_thread_messages()
        
    Returns:
        str: Formatted thread content
    """
    if not thread_messages:
        return ""
    
    thread_lines = []
    
    for i, message in enumerate(thread_messages):
        # Get message content
        body_text = message.get('body_text', '')
        if not body_text and message.get('body_html'):
            body_text = convert_html_to_clean_text(message['body_html'])
        
        if not body_text:
            continue  # Skip messages with no content
        
        # Clean the body content
        cleaned_body = clean_email_body(body_text)
        
        # Extract new content (remove quotes from this message)
        new_content = extract_new_content(cleaned_body)
        
        if not new_content.strip():
            continue  # Skip empty messages
        
        # Format message
        from_header = message.get('from', 'Unknown')
        date = message.get('date', '')
        
        # Add message separator and metadata
        if i > 0:
            thread_lines.append("\n---\n")
        
        thread_lines.append(f"From: {from_header}")
        if date:
            thread_lines.append(f"Date: {date}")
        thread_lines.append("")  # Empty line
        thread_lines.append(new_content)
    
    return "\n".join(thread_lines)


def summarize_thread_content(thread_content: str) -> Optional[str]:
    """
    Summarize thread content using the proxy service LLM.
    
    Args:
        thread_content: Full thread content to summarize
        
    Returns:
        str: Summarized thread content or None if summarization fails
    """
    try:
        # Load the thread summarization prompt
        prompt = load_prompt("googleapi", "gmail", "thread_summary", 
                            thread_content=thread_content,
                            target_words=THREAD_SUMMARY_TARGET_WORDS)
        
        # Create request for proxy service
        singleturn_request = SingleTurnRequest(
            model="default",  # Use default model for summarization
            prompt=prompt
        )
        
        # Send to proxy service
        proxy_port = os.getenv("PROXY_PORT", 4205)
        timeout = 30.0
        
        async def make_request():
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"http://proxy:{proxy_port}/api/singleturn",
                    json=singleturn_request.model_dump()
                )
                response.raise_for_status()
                return response.json()
        
        # Use asyncio to run the async request
        import asyncio
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context, create a new loop in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, make_request())
                    proxy_response = future.result(timeout=timeout)
            else:
                # We can run directly
                proxy_response = loop.run_until_complete(make_request())
        except RuntimeError:
            # No event loop, create one
            proxy_response = asyncio.run(make_request())
        
        summary = proxy_response.get("response", "").strip()
        if not summary:
            logger.warning("Proxy service returned empty summary")
            return None
        
        logger.info(f"Thread summarized: {len(thread_content.split())} -> {len(summary.split())} words")
        return summary
        
    except Exception as e:
        logger.error(f"Failed to summarize thread content: {e}")
        return None


def format_email_for_brain_prompt(cleaned_email: Dict[str, Any]) -> str:
    """
    Format cleaned email data into a structured prompt for the brain service.
    
    Args:
        cleaned_email: Cleaned email data from clean_email_for_brain()
        
    Returns:
        str: Formatted email content optimized for LLM processing
    """
    lines = []
    
    # Basic email headers
    lines.append(f"From: {cleaned_email['from']}")
    lines.append(f"Subject: {cleaned_email['subject']}")
    
    # Additional headers if present
    if cleaned_email.get('cc'):
        lines.append(f"Cc: {cleaned_email['cc']}")
    if cleaned_email.get('date'):
        lines.append(f"Date: {cleaned_email['date']}")
    
    # Add metadata for context
    if cleaned_email.get('is_reply'):
        lines.append("(This appears to be a reply to a previous email)")
    
    # Add thread context if available
    if cleaned_email.get('has_thread_context') and cleaned_email.get('thread_summary'):
        lines.append("")
        lines.append("Previous conversation context:")
        lines.append(cleaned_email['thread_summary'])
        lines.append("")
        lines.append("--- Current email ---")
    
    lines.append("")  # Empty line before content
    
    # Email content
    body = cleaned_email.get('body_cleaned', '')
    if body:
        lines.append("Content:")
        lines.append(body)
    else:
        # Fallback to snippet if no body content
        snippet = cleaned_email.get('snippet', '')
        if snippet:
            lines.append("Content (preview):")
            lines.append(snippet)
    
    return "\n".join(lines)


def clean_email_body(email_body: str) -> str:
    """
    Clean up email body text by removing formatting artifacts and normalizing whitespace.
    
    Args:
        email_body: Raw email body text
        
    Returns:
        str: Cleaned email body text
    """
    if not email_body:
        return ""
    
    text = email_body
    
    # Normalize line endings
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    
    # Remove excessive whitespace
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines
    
    # Remove common email artifacts
    text = re.sub(r'\[cid:[^\]]+\]', '', text)  # CID references (inline images)
    text = re.sub(r'<[^>]+>', '', text)  # Any remaining HTML tags
    
    # Clean up URLs (replace with placeholder to reduce noise)
    text = re.sub(r'https?://\S+', '[URL]', text)
    
    # Remove email signature separators
    text = re.sub(r'^--\s*$', '', text, flags=re.MULTILINE)
    
    return text.strip()


def extract_new_content(email_body: str) -> str:
    """
    Extract just the new content from an email, removing quoted previous messages.
    
    This uses pattern matching to identify common reply separators and extracts
    only the new content written by the sender.
    
    Args:
        email_body: Full email body text
        
    Returns:
        str: Just the new content without quoted replies
    """
    if not email_body:
        return ""
    
    # Common patterns that indicate quoted content starts
    quote_patterns = [
        r'^On .+, .+ wrote:.*$',  # "On Date, Person wrote:"
        r'^From: .+$',            # "From: person@email.com"  
        r'^Sent: .+$',            # "Sent: date/time"
        r'^To: .+$',              # "To: recipient"
        r'^Subject: .+$',         # "Subject: Re: topic"
        r'^Date: .+$',            # "Date: timestamp"
        r'^>.*$',                 # Lines starting with >
        r'^\s*-+\s*Original Message\s*-+.*$',  # Outlook style
        r'^\s*-+\s*Forwarded message\s*-+.*$', # Forwarded message
        r'^\s*_{5,}.*$',          # Long underscores
        r'^\s*={5,}.*$',          # Long equals signs
        r'^\s*\*{5,}.*$',         # Long asterisks
    ]
    
    lines = email_body.split('\n')
    new_content_lines = []
    
    for line in lines:
        # Check if this line matches any quote pattern
        is_quote_start = any(re.match(pattern, line.strip(), re.IGNORECASE) 
                           for pattern in quote_patterns)
        
        if is_quote_start:
            break  # Stop processing at first quote separator
        
        new_content_lines.append(line)
    
    new_content = '\n'.join(new_content_lines).strip()
    
    # If we extracted very little content, return the original
    # (might be a short email without quotes)
    if len(new_content) < 20 and len(email_body) > len(new_content) * 2:
        return email_body.strip()
    
    return new_content


def convert_html_to_clean_text(html_content: str) -> str:
    """
    Convert HTML email content to clean, readable text.
    
    This is a basic HTML-to-text converter that removes tags and cleans up
    common HTML artifacts without requiring external dependencies.
    
    Args:
        html_content: HTML email content
        
    Returns:
        str: Clean text version
    """
    if not html_content:
        return ""
    
    text = html_content
    
    # Remove script and style elements completely
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert common HTML elements to text equivalents
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<div[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '', text, flags=re.IGNORECASE)
    
    # Handle lists
    text = re.sub(r'<li[^>]*>', '\n• ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '', text, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()


def detect_if_reply(body: str, subject: str) -> bool:
    """
    Detect if an email appears to be a reply to a previous message.
    
    Args:
        body: Email body content
        subject: Email subject line
        
    Returns:
        bool: True if this appears to be a reply
    """
    # Check subject line for reply indicators
    if subject:
        subject_lower = subject.lower()
        if any(prefix in subject_lower for prefix in ['re:', 'fwd:', 'fw:']):
            return True
    
    # Check body content for reply patterns
    if body:
        body_lower = body.lower()
        reply_indicators = [
            'wrote:',
            'said:',
            'sent:',
            'from:',
            'on ' and ' wrote',
            'thank you for',
            'thanks for',
        ]
        
        if any(indicator in body_lower for indicator in reply_indicators):
            return True
    
    return False


def get_email_summary_stats(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate summary statistics about the email for logging and monitoring.
    
    Args:
        email_data: Email data (raw or cleaned)
        
    Returns:
        Dict with summary statistics
    """
    body = email_data.get('body_cleaned') or email_data.get('body', {}).get('text', '')
    
    return {
        'has_html': bool(email_data.get('body', {}).get('html')),
        'has_text': bool(email_data.get('body', {}).get('text')),
        'word_count': len(body.split()) if body else 0,
        'char_count': len(body) if body else 0,
        'is_reply': email_data.get('is_reply', False),
        'has_attachments': bool(email_data.get('attachments')),
        'thread_id': email_data.get('threadId'),
        'has_thread_context': email_data.get('has_thread_context', False),
        'thread_summary_words': len(email_data.get('thread_summary', '').split()) if email_data.get('thread_summary') else 0,
    }
