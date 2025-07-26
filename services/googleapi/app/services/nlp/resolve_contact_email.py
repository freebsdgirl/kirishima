"""
This module provides a function to resolve a contact identifier (either a contact name or an email address)
to an actual email address using the contacts service.
Functions:
    resolve_contact_email(contact_identifier: str) -> str:
        Resolves a contact name or email to an actual email address.
        If the identifier is already an email address, it is returned as-is.
        Otherwise, it searches through all contacts for a matching name and returns the associated email address.
        Raises an HTTPException if the contact cannot be found or resolved.
"""
from fastapi import HTTPException

from app.services.contacts.contacts import list_all_contacts

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")


async def resolve_contact_email(contact_identifier: str) -> str:
    """
    Resolve a contact name or email to an actual email address.
    
    Args:
        contact_identifier: Either an email address or contact name
        
    Returns:
        str: Resolved email address
        
    Raises:
        HTTPException: If contact cannot be found or resolved
    """
    # If it's already an email address, return as-is
    if "@" in contact_identifier:
        return contact_identifier
        
    # Try to find contact by name - search through all contacts
    try:
        contacts_response = list_all_contacts()
        for contact in contacts_response.contacts:
            # Check if the name matches (case-insensitive)
            for name in contact.names:
                if (name.display_name and contact_identifier.lower() in name.display_name.lower()) or \
                   (name.given_name and name.family_name and 
                    contact_identifier.lower() in f"{name.given_name} {name.family_name}".lower()):
                    # Found a match, return the primary email
                    if contact.email_addresses:
                        # Return the primary email address
                        primary_email = next(
                            (email.value for email in contact.email_addresses if email.type == "primary"),
                            None
                        )
                        if primary_email:
                            return primary_email
                        # Fallback to first available email
                        return contact.email_addresses[0].value
                        
    except Exception as e:
        logger.warning(f"Could not resolve contact '{contact_identifier}': {e}")
        
    raise HTTPException(
        status_code=404,
        detail=f"Could not find email address for contact: {contact_identifier}"
    )