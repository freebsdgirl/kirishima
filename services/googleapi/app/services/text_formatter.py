import pytz
from dateutil import parser as date_parser
"""
This module provides utility functions to format and clean Google API data
for human-readable output. It includes functions to:
- Remove HTML tags from text.
- Format Google Calendar event datetimes into readable strings.
- Convert lists of Google Calendar events, emails, and contacts into
    readable summaries suitable for display or messaging.
Functions:
        clean_html_from_text(text: str) -> str:
                Removes HTML tags and cleans up text content.
        format_datetime_readable(dt_dict: Dict[str, Any]) -> str:
                Formats a Google Calendar datetime dictionary into a human-readable string.
        format_events_readable(events: List[Dict[str, Any]]) -> str:
                Converts a list of Google Calendar event dictionaries into a readable string.
        format_emails_readable(emails: List[Dict[str, Any]]) -> str:
                Converts a list of email dictionaries into a readable string.
        format_contacts_readable(contacts: List[Dict[str, Any]]) -> str:
                Converts a list of contact dictionaries into a readable string.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime


def clean_html_from_text(text: str) -> str:
    """
    Remove HTML tags and clean up text content.
    
    Args:
        text: Text that may contain HTML
        
    Returns:
        Cleaned text without HTML
    """
    if not text:
        return text
    
    # Remove HTML links like <https://example.com>
    text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
    
    # Remove other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up excessive whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 consecutive newlines
    text = re.sub(r' +', ' ', text)  # Multiple spaces to single space
    
    return text.strip()


def format_datetime_readable(dt_dict: Dict[str, Any]) -> str:
    """
    Format a Google Calendar datetime dict to human-readable format.
    
    Args:
        dt_dict: Dictionary with 'dateTime' or 'date' field
        
    Returns:
        Human-readable date/time string
    """
    if not dt_dict:
        return "No time specified"
    
    if 'dateTime' in dt_dict:
        # Parse ISO datetime
        dt_str = dt_dict['dateTime']
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime("%a %b %d, %Y at %I:%M%p")
        except:
            return dt_str
    elif 'date' in dt_dict:
        # All-day event
        date_str = dt_dict['date']
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%a %b %d, %Y (all day)")
        except:
            return date_str
    
    return str(dt_dict)


def format_events_readable(events: List[Dict[str, Any]]) -> str:
    """
    Convert calendar events to human-readable format.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        Human-readable string representation of events
    """
    if not events:
        return "No events found."
    
    readable_events = []
    
    for i, event in enumerate(events, 1):
        lines = [f"{i}. {event.get('summary', 'Untitled Event')}"]

        # Add time info
        start = event.get('start')
        end = event.get('end')
        if start:
            start_str = format_datetime_readable(start)
            if end:
                end_str = format_datetime_readable(end)
                # If same date, just show time range
                if start_str.split(' at ')[0] == end_str.split(' at ')[0]:
                    try:
                        start_time = start_str.split(' at ')[1]
                        end_time = end_str.split(' at ')[1]
                        lines.append(f"   Time: {start_str.split(' at ')[0]} from {start_time} to {end_time}")
                    except:
                        lines.append(f"   Time: {start_str} to {end_str}")
                else:
                    lines.append(f"   Time: {start_str} to {end_str}")
            else:
                lines.append(f"   Time: {start_str}")

        # Location intentionally omitted from readable output

        # Add description if present (cleaned and truncated)
        description = event.get('description')
        if description:
            description = clean_html_from_text(description)
            # Truncate long descriptions
            if len(description) > 200:
                description = description[:200] + "..."
            lines.append(f"   Details: {description}")

        # Add status if not confirmed
        status = event.get('status')
        if status and status != 'confirmed':
            lines.append(f"   Status: {status}")

        readable_events.append('\n'.join(lines))
    
    return '\n\n'.join(readable_events)


def format_emails_readable(emails: List[Dict[str, Any]]) -> str:
    # Post-filter by local date range if present in the first email dict
    if emails and isinstance(emails[0], dict) and 'local_date_range' in emails[0]:
        local_date_range = emails[0]['local_date_range']
        emails = filter_emails_by_local_date(emails, local_date_range)
    """
    Convert emails to human-readable format.
    
    Args:
        emails: List of email dictionaries
        
    Returns:
        Human-readable string representation of emails
    """
    if not emails:
        return "No emails found."
    
    readable_emails = []
    
    for i, email in enumerate(emails, 1):
        lines = [f"{i}. {email.get('subject', 'No Subject')}"]

        # Add email ID
        email_id = email.get('id')
        if email_id:
            lines.append(f"   ID: {email_id}")

        # Add sender and date
        from_addr = email.get('from', 'Unknown sender')
        date = email.get('date', 'Unknown date')
        lines.append(f"   From: {from_addr}")
        lines.append(f"   Date: {date}")

        # Add snippet or cleaned body
        content = email.get('body_cleaned') or email.get('snippet', '')
        if content:
            # For get_email_by_id, show the full cleaned body (do not truncate)
            if len(emails) == 1 and email.get('body_cleaned'):
                lines.append(f"   Content: {content}")
            else:
                # Truncate long content for search_emails
                if len(content) > 150:
                    content = content[:150] + "..."
                lines.append(f"   Content: {content}")

        # Add reply indicator
        if email.get('is_reply'):
            lines.append("   [This is a reply]")

        # Add thread summary if present
        thread_summary = email.get('thread_summary')
        if thread_summary:
            lines.append(f"   Thread context: {thread_summary}")

        readable_emails.append('\n'.join(lines))
    
    return '\n\n'.join(readable_emails)


def filter_emails_by_local_date(emails: List[Dict[str, Any]], local_date_range: dict) -> List[Dict[str, Any]]:
    """
    Filter emails to only those whose date (in local time) falls within the given local_date_range.
    local_date_range should be a dict with 'start', 'end', and 'timezone' keys.
    """
    tz = pytz.timezone(local_date_range.get('timezone', 'UTC'))
    start = date_parser.parse(local_date_range['start']).astimezone(tz)
    end = date_parser.parse(local_date_range['end']).astimezone(tz)
    filtered = []
    for email in emails:
        date_str = email.get('date')
        if not date_str:
            continue
        try:
            dt = date_parser.parse(date_str)
            dt_local = dt.astimezone(tz)
            if start <= dt_local < end:
                filtered.append(email)
        except Exception:
            continue
    return filtered


def format_contacts_readable(contacts: List[Dict[str, Any]]) -> str:
    """
    Convert contacts to human-readable format.
    
    Args:
        contacts: List of contact dictionaries
        
    Returns:
        Human-readable string representation of contacts
    """
    if not contacts:
        return "No contacts found."
    
    readable_contacts = []
    
    for i, contact in enumerate(contacts, 1):
        # Get display name
        display_name = "Unknown Contact"
        if contact.get('names'):
            for name in contact['names']:
                if name.get('display_name'):
                    display_name = name['display_name']
                    break
        
        lines = [f"{i}. {display_name}"]
        
        # Add email addresses
        if contact.get('email_addresses'):
            emails = []
            for email in contact['email_addresses']:
                email_value = email.get('value', '')
                email_type = email.get('type', '').lower() if email.get('type') else ''
                if email_type:
                    emails.append(f"{email_value} ({email_type})")
                else:
                    emails.append(email_value)
            if emails:
                lines.append(f"   Email: {', '.join(emails)}")
        
        # Add phone numbers
        if contact.get('phone_numbers'):
            phones = []
            for phone in contact['phone_numbers']:
                phone_value = phone.get('value', '')
                phone_type = phone.get('type', '').lower() if phone.get('type') else ''
                if phone_type:
                    phones.append(f"{phone_value} ({phone_type})")
                else:
                    phones.append(phone_value)
            if phones:
                lines.append(f"   Phone: {', '.join(phones)}")
        
        # Add notes from biographies
        if contact.get('biographies'):
            for biography in contact['biographies']:
                if isinstance(biography, dict) and biography.get('value'):
                    lines.append(f"   Notes: {biography['value']}")
                    break  # Only show the first/primary note
        
        # Add addresses (simplified)
        if contact.get('addresses'):
            for address in contact['addresses']:
                if isinstance(address, dict) and address.get('formatted_value'):
                    address_type = address.get('type', '').lower() if address.get('type') else ''
                    if address_type:
                        lines.append(f"   Address ({address_type}): {address['formatted_value']}")
                    else:
                        lines.append(f"   Address: {address['formatted_value']}")
                    break  # Only show the first address
        
        readable_contacts.append('\n'.join(lines))
    
    return '\n\n'.join(readable_contacts)
