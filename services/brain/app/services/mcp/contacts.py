"""
Contacts MCP tool for managing Google Contacts.

Provides parameter-based interface to Google Contacts functionality including:
- get_contact: Retrieve a specific contact by email
- list_contacts: List all contacts
- search_contacts: Search contacts by query  
- create_contact: Create a new contact
- update_contact: Update an existing contact
- delete_contact: Delete a contact

Returns formatted strings instead of JSON to save tokens.
"""

import httpx
import json
from typing import Dict, Any, List
from shared.models.mcp import MCPToolResponse

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

# Load config for service communication
with open('/app/config/config.json') as f:
    config = json.load(f)

GOOGLEAPI_BASE_URL = "http://googleapi:4215"
TIMEOUT = config.get("timeout", 30)


def format_contact_info(contacts_data: List[Dict[str, Any]]) -> str:
    """Format contact data into readable string to save tokens."""
    if not contacts_data:
        return "No contacts found."
    
    readable_contacts = []
    
    for i, contact in enumerate(contacts_data, 1):
        # Get display name
        display_name = "Unknown Contact"
        if contact.get('names'):
            for name in contact['names']:
                if name.get('display_name'):
                    display_name = name['display_name']
                    break
        
        lines = [f"{i}. {display_name}"]
        
        # Add emails
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
        
        # Add phones
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
        
        # Add notes
        if contact.get('biographies'):
            for biography in contact['biographies']:
                if isinstance(biography, dict) and biography.get('value'):
                    lines.append(f"   Notes: {biography['value']}")
                    break
        
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


async def get_contact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get a specific contact by email address."""
    email = params.get("email")
    if not email:
        return {"status": "error", "message": "Email parameter is required"}
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{GOOGLEAPI_BASE_URL}/contacts/{email}")
            
            if response.status_code == 404:
                return {
                    "status": "error",
                    "message": f"Contact not found: {email}"
                }
            elif response.status_code != 200:
                return {
                    "status": "error", 
                    "message": f"Failed to get contact: {response.status_code} {response.text}"
                }
            
            contact_data = response.json()
            contact_info = format_contact_info([contact_data])
            
            return {
                "status": "success",
                "message": "Contact found",
                "contact_info": contact_info
            }
            
    except Exception as e:
        logger.error(f"Error getting contact {email}: {e}")
        return {"status": "error", "message": f"Failed to get contact: {str(e)}"}


async def list_contacts(params: Dict[str, Any]) -> Dict[str, Any]:
    """List all contacts from the cache."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{GOOGLEAPI_BASE_URL}/contacts/")
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Failed to list contacts: {response.status_code} {response.text}"
                }
            
            data = response.json()
            contacts_data = data.get("contacts", [])
            
            if not contacts_data:
                return {
                    "status": "success",
                    "message": "No contacts found",
                    "count": 0,
                    "contacts_info": "No contacts found."
                }
            
            contacts_info = format_contact_info(contacts_data)
            
            return {
                "status": "success",
                "message": f"Retrieved {len(contacts_data)} contacts",
                "count": len(contacts_data),
                "contacts_info": contacts_info
            }
            
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        return {"status": "error", "message": f"Failed to list contacts: {str(e)}"}


async def search_contacts(params: Dict[str, Any]) -> Dict[str, Any]:
    """Search contacts by query string."""
    query = params.get("query")
    if not query:
        return {"status": "error", "message": "Query parameter is required"}
    
    max_results = params.get("max_results", 25)
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            search_data = {
                "query": query,
                "max_results": max_results
            }
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/contacts/search", json=search_data)
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Failed to search contacts: {response.status_code} {response.text}"
                }
            
            data = response.json()
            contacts_data = data.get("contacts", [])
            
            if not contacts_data:
                return {
                    "status": "success",
                    "message": f"No contacts found matching '{query}'",
                    "count": 0,
                    "contacts_info": "No contacts found."
                }
            
            contacts_info = format_contact_info(contacts_data)
            
            return {
                "status": "success",
                "message": f"Found {len(contacts_data)} contacts matching '{query}'",
                "count": len(contacts_data),
                "contacts_info": contacts_info
            }
            
    except Exception as e:
        logger.error(f"Error searching contacts for '{query}': {e}")
        return {"status": "error", "message": f"Failed to search contacts: {str(e)}"}


async def create_contact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new contact."""
    # Build the create request payload
    contact_data = {}
    
    # Add name fields
    if any(params.get(field) for field in ['display_name', 'given_name', 'family_name', 'middle_name']):
        contact_data['display_name'] = params.get('display_name')
        contact_data['given_name'] = params.get('given_name')
        contact_data['family_name'] = params.get('family_name')
        contact_data['middle_name'] = params.get('middle_name')
    
    # Add email addresses
    if params.get('email_addresses'):
        contact_data['email_addresses'] = params['email_addresses']
    
    # Add phone numbers  
    if params.get('phone_numbers'):
        contact_data['phone_numbers'] = params['phone_numbers']
    
    # Add notes
    if params.get('notes'):
        contact_data['notes'] = params['notes']
    
    if not contact_data:
        return {"status": "error", "message": "At least one contact field is required"}
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"{GOOGLEAPI_BASE_URL}/contacts/", json=contact_data)
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Failed to create contact: {response.status_code} {response.text}"
                }
            
            data = response.json()
            contact_name = params.get('display_name') or params.get('given_name') or 'Contact'
            
            # Format the created contact
            contact_info = ""
            if data.get("contact"):
                contact_info = format_contact_info([data["contact"]])
            
            return {
                "status": "success",
                "message": f"Contact '{contact_name}' created successfully",
                "resource_name": data.get("resource_name"),
                "contact_info": contact_info
            }
            
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        return {"status": "error", "message": f"Failed to create contact: {str(e)}"}


async def update_contact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing contact."""
    contact_identifier = params.get("contact_identifier")
    if not contact_identifier:
        return {"status": "error", "message": "Contact identifier is required"}
    
    # Build the update request payload
    update_data = {"contact_identifier": contact_identifier}
    
    # Add fields to update
    for field in ['display_name', 'given_name', 'family_name', 'middle_name', 'notes']:
        if params.get(field):
            update_data[field] = params[field]
    
    if params.get('email_addresses'):
        update_data['email_addresses'] = params['email_addresses']
    
    if params.get('phone_numbers'):
        update_data['phone_numbers'] = params['phone_numbers']
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.put(f"{GOOGLEAPI_BASE_URL}/contacts/update", json=update_data)
            
            if response.status_code == 404:
                return {
                    "status": "error",
                    "message": f"Contact not found: {contact_identifier}"
                }
            elif response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Failed to update contact: {response.status_code} {response.text}"
                }
            
            data = response.json()
            
            # Format the updated contact
            contact_info = ""
            if data.get("contact"):
                contact_info = format_contact_info([data["contact"]])
            
            return {
                "status": "success",
                "message": f"Contact '{contact_identifier}' updated successfully",
                "resource_name": data.get("resource_name"),
                "contact_info": contact_info
            }
            
    except Exception as e:
        logger.error(f"Error updating contact {contact_identifier}: {e}")
        return {"status": "error", "message": f"Failed to update contact: {str(e)}"}


async def delete_contact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a contact by identifier."""
    contact_identifier = params.get("contact_identifier")
    if not contact_identifier:
        return {"status": "error", "message": "Contact identifier is required"}
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # URL encode the contact identifier to handle special characters like @
            import urllib.parse
            encoded_identifier = urllib.parse.quote(contact_identifier, safe='')
            response = await client.delete(f"{GOOGLEAPI_BASE_URL}/contacts/delete/{encoded_identifier}")
            
            if response.status_code == 404:
                return {
                    "status": "error",
                    "message": f"Contact not found: {contact_identifier}"
                }
            elif response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Failed to delete contact: {response.status_code} {response.text}"
                }
            
            data = response.json()
            
            return {
                "status": "success",
                "message": f"Contact '{contact_identifier}' deleted successfully",
                "resource_name": data.get("resource_name")
            }
            
    except Exception as e:
        logger.error(f"Error deleting contact {contact_identifier}: {e}")
        return {"status": "error", "message": f"Failed to delete contact: {str(e)}"}


async def contacts(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Main contacts tool dispatcher.
    
    Supported actions:
    - get_contact: Retrieve a specific contact by email
    - list_contacts: List all contacts  
    - search_contacts: Search contacts by query
    - create_contact: Create a new contact
    - update_contact: Update an existing contact
    - delete_contact: Delete a contact
    """
    action = parameters.get("action")
    if not action:
        return MCPToolResponse(
            success=False,
            result=None,
            error="Action parameter is required"
        )
    
    logger.info(f"Executing contacts action: {action}")
    
    try:
        if action == "get_contact":
            result = await get_contact(parameters)
        elif action == "list_contacts":
            result = await list_contacts(parameters)
        elif action == "search_contacts":
            result = await search_contacts(parameters)
        elif action == "create_contact":
            result = await create_contact(parameters)
        elif action == "update_contact":
            result = await update_contact(parameters)
        elif action == "delete_contact":
            result = await delete_contact(parameters)
        else:
            return MCPToolResponse(
                success=False,
                result=None,
                error=f"Unknown contacts action: {action}"
            )
        
        success = result.get("status") == "success"
        if success:
            return MCPToolResponse(success=True, result=result, error=None)
        else:
            return MCPToolResponse(success=False, result=None, error=result.get("message"))
            
    except Exception as e:
        logger.error(f"Error executing contacts action {action}: {e}")
        return MCPToolResponse(
            success=False,
            result=None,
            error=f"Failed to execute contacts action: {str(e)}"
        )
