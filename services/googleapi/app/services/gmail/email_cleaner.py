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
from typing import Dict, Any, Optional, Tuple
from shared.log_config import get_logger

logger = get_logger(f"googleapi.{__name__}")

def clean_email_for_brain(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and process email data before sending to brain service.
    
    This function takes raw email data from Gmail API and returns a cleaned
    version optimized for LLM processing, with reduced noise and better structure.
    
    Args:
        email_data: Raw email data from Gmail API containing headers and body
        
    Returns:
        Dict with cleaned email data and metadata for brain processing
    """
    # Extract basic email information
    subject = email_data.get('subject', 'No Subject')
    from_header = email_data.get('from', '')
    body_data = email_data.get('body', {})
    body_text = body_data.get('text', '')
    body_html = body_data.get('html', '')
    
    # Use HTML content if text is not available
    if not body_text and body_html:
        body_text = convert_html_to_clean_text(body_html)
    
    # Clean the email body content
    cleaned_body = clean_email_body(body_text) if body_text else email_data.get('snippet', '')
    
    # Extract just the new content (remove quoted replies)
    new_content = extract_new_content(cleaned_body)
    
    # Determine if this is likely a reply
    is_reply = detect_if_reply(new_content, subject)
    
    # Create cleaned email data
    cleaned_data = {
        'id': email_data.get('id'),
        'threadId': email_data.get('threadId'),
        'subject': subject,
        'from': from_header,
        'to': email_data.get('to', ''),
        'cc': email_data.get('cc', ''),
        'date': email_data.get('date', ''),
        'body_cleaned': new_content,
        'body_full': cleaned_body,  # Keep full content for reference
        'snippet': email_data.get('snippet', ''),
        'is_reply': is_reply,
        'word_count': len(new_content.split()) if new_content else 0
    }
    
    logger.debug(f"Cleaned email {email_data.get('id', 'unknown')}: "
                f"{cleaned_data['word_count']} words, is_reply={is_reply}")
    
    return cleaned_data


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
    }
