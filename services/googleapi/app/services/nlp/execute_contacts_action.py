"""
This module provides the `_execute_contacts_action` asynchronous function, which executes various contact-related actions such as retrieving, listing, searching, creating, updating, and deleting contacts. It acts as a dispatcher for contact operations, handling input parameters, invoking the appropriate service functions, and formatting the results for API responses.
Functions:
    _execute_contacts_action(action: str, params: Dict[str, Any], readable: bool = False) -> Dict[str, Any]:
        Executes a specified contact action based on the provided action string and parameters.
        Supported actions:
            - "get_contact": Retrieve a contact by email.
            - "list_contacts": List all contacts.
            - "search_contacts": Search for contacts by query, with optional human-readable formatting.
            - "create_contact": Create a new contact with provided details.
            - "update_contact": Update an existing contact's information.
            - "delete_contact": Delete a contact by identifier.
        Raises:
            HTTPException: If the action is unknown or if a contact is not found.
        Returns:
            A dictionary containing the result of the action, such as contact data, success status, messages, and counts.
"""

from typing import Dict, Any
from fastapi import HTTPException
from shared.models.googleapi import (
    SearchContactsRequest,
    CreateContactRequest,
    UpdateContactRequest,
    DeleteContactRequest
)

from app.services.text_formatter import format_contacts_readable
from app.services.contacts.contacts import get_contact_by_email, list_all_contacts, search_contacts, create_contact, update_contact, delete_contact

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")


async def _execute_contacts_action(action: str, params: Dict[str, Any], readable: bool = False) -> Dict[str, Any]:
    """Execute Contacts-specific actions."""
    if action == "get_contact":
        contact = get_contact_by_email(params["email"])
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        return {
            "contact": contact.model_dump(),
            "message": "Contact found"
        }
        
    elif action == "list_contacts":
        result = list_all_contacts()
        return {
            "contacts": [contact.model_dump() for contact in result.contacts],
            "count": len(result.contacts)
        }
        
    elif action == "search_contacts":
        search_request = SearchContactsRequest(
            query=params["query"],
            max_results=params.get("max_results", 25)
        )
        result = search_contacts(search_request)
        
        if readable:
            # Return human-readable format
            contacts_data = [contact.model_dump() for contact in result.contacts] if result.contacts else []
            readable_text = format_contacts_readable(contacts_data)
            return {
                "result": readable_text,
                "count": len(result.contacts) if result.contacts else 0,
                "success": result.success,
                "message": result.message
            }
        else:
            return {
                "success": result.success,
                "message": result.message,
                "contacts": [contact.model_dump() for contact in result.contacts] if result.contacts else [],
                "count": len(result.contacts) if result.contacts else 0
            }
        
    elif action == "create_contact":
        # Build the CreateContactRequest from params
        email_addresses = []
        if params.get("email_addresses"):
            for email_data in params["email_addresses"]:
                email_addresses.append({
                    "value": email_data.get("value"),
                    "type": email_data.get("type", "other")
                })
        
        phone_numbers = []
        if params.get("phone_numbers"):
            for phone_data in params["phone_numbers"]:
                phone_numbers.append({
                    "value": phone_data.get("value"),
                    "type": phone_data.get("type", "other")
                })
        
        create_request = CreateContactRequest(
            display_name=params.get("display_name"),
            given_name=params.get("given_name"),
            family_name=params.get("family_name"),
            middle_name=params.get("middle_name"),
            email_addresses=email_addresses if email_addresses else None,
            phone_numbers=phone_numbers if phone_numbers else None,
            notes=params.get("notes")
        )
        
        result = create_contact(create_request)
        return {
            "success": result.success,
            "message": result.message,
            "contact": result.contact.model_dump() if result.contact else None,
            "resource_name": result.resource_name
        }
        
    elif action == "update_contact":
        # Build the UpdateContactRequest from params
        email_addresses = []
        if params.get("email_addresses"):
            for email_data in params["email_addresses"]:
                email_addresses.append({
                    "value": email_data.get("value"),
                    "type": email_data.get("type", "other")
                })
        
        phone_numbers = []
        if params.get("phone_numbers"):
            for phone_data in params["phone_numbers"]:
                phone_numbers.append({
                    "value": phone_data.get("value"),
                    "type": phone_data.get("type", "other")
                })
        
        update_request = UpdateContactRequest(
            contact_identifier=params["contact_identifier"],
            display_name=params.get("display_name"),
            given_name=params.get("given_name"),
            family_name=params.get("family_name"),
            middle_name=params.get("middle_name"),
            email_addresses=email_addresses if email_addresses else None,
            phone_numbers=phone_numbers if phone_numbers else None,
            notes=params.get("notes")
        )
        
        result = update_contact(update_request)
        return {
            "success": result.success,
            "message": result.message,
            "contact": result.contact.model_dump() if result.contact else None,
            "resource_name": result.resource_name
        }
        
    elif action == "delete_contact":
        delete_request = DeleteContactRequest(
            contact_identifier=params["contact_identifier"]
        )
        result = delete_contact(delete_request)
        return {
            "success": result.success,
            "message": result.message,
            "resource_name": result.resource_name
        }
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown Contacts action: {action}")
