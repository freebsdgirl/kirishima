"""
Google Contacts service implementation.

This module provides functions for interacting with the Google People API
to manage contacts, including fetching, caching, and retrieving contact information.

Functions:
    refresh_contacts_cache(): Refreshes the local contacts cache from Google API.
    get_admin_contact(): Gets the admin contact configured in config.json.
    get_contact_by_email(): Gets a contact by email address (from cache or API).
    list_all_contacts(): Lists all contacts (from cache or API).
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.contacts.auth import get_people_service
from app.services.contacts.database import (
    cache_contacts, get_cached_contact_by_email, get_all_cached_contacts,
    clear_contacts_cache, get_cache_stats, cache_contact
)
from app.services.gmail.util import get_config
from shared.models.googleapi import GoogleContact, ContactsListResponse, RefreshCacheResponse, CreateContactRequest, CreateContactResponse, SearchContactsRequest, UpdateContactRequest, DeleteContactRequest, ContactResponse

from typing import Optional, List, Dict, Any
from datetime import datetime
import json


def _convert_contact_data(contact_data: Dict[str, Any]) -> GoogleContact:
    """
    Convert Google People API contact data to our GoogleContact model.
    
    Args:
        contact_data: Raw contact data from Google People API
        
    Returns:
        GoogleContact: Converted contact data
    """
    # Extract and convert names
    names = []
    for name_data in contact_data.get('names', []):
        names.append({
            'display_name': name_data.get('displayName'),
            'given_name': name_data.get('givenName'),
            'family_name': name_data.get('familyName'),
            'middle_name': name_data.get('middleName')
        })
    
    # Extract and convert email addresses
    email_addresses = []
    for email_data in contact_data.get('emailAddresses', []):
        email_addresses.append({
            'value': email_data.get('value', ''),
            'type': email_data.get('type'),
            'metadata': email_data.get('metadata')
        })
    
    # Extract and convert phone numbers
    phone_numbers = []
    for phone_data in contact_data.get('phoneNumbers', []):
        phone_numbers.append({
            'value': phone_data.get('value', ''),
            'type': phone_data.get('type'),
            'metadata': phone_data.get('metadata')
        })
    
    # Extract and convert addresses
    addresses = []
    for address_data in contact_data.get('addresses', []):
        addresses.append({
            'formatted_value': address_data.get('formattedValue'),
            'street_address': address_data.get('streetAddress'),
            'city': address_data.get('city'),
            'region': address_data.get('region'),
            'postal_code': address_data.get('postalCode'),
            'country': address_data.get('country'),
            'type': address_data.get('type')
        })
    
    # Extract metadata
    metadata = contact_data.get('metadata', {})
    sources = metadata.get('sources', [])
    created_time = sources[0].get('updateTime') if sources else None
    modified_time = sources[0].get('updateTime') if sources else None
    
    return GoogleContact(
        resource_name=contact_data.get('resourceName', ''),
        etag=contact_data.get('etag'),
        names=names if names else None,
        email_addresses=email_addresses if email_addresses else None,
        phone_numbers=phone_numbers if phone_numbers else None,
        addresses=addresses if addresses else None,
        organizations=contact_data.get('organizations'),
        birthdays=contact_data.get('birthdays'),
        biographies=contact_data.get('biographies'),
        photos=contact_data.get('photos'),
        metadata=metadata,
        created_time=created_time,
        modified_time=modified_time
    )


def refresh_contacts_cache() -> RefreshCacheResponse:
    """
    Refresh the local contacts cache by fetching all contacts from Google API.
    
    Returns:
        RefreshCacheResponse: Status of the cache refresh operation
    """
    try:
        logger.info("Starting contacts cache refresh")
        
        # Get People API service
        service = get_people_service()
        
        # Clear existing cache
        clear_contacts_cache()
        
        # Fetch all contacts
        all_contacts = []
        next_page_token = None
        
        while True:
            # Request contacts with all available fields
            request_body = {
                'pageSize': 1000,  # Max page size
                'personFields': ','.join([
                    'names', 'emailAddresses', 'phoneNumbers', 'addresses',
                    'organizations', 'birthdays', 'biographies', 'photos', 'metadata'
                ])
            }
            
            if next_page_token:
                request_body['pageToken'] = next_page_token
            
            result = service.people().connections().list(
                resourceName='people/me',
                **request_body
            ).execute()
            
            connections = result.get('connections', [])
            all_contacts.extend(connections)
            
            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break
        
        # Cache all contacts
        if all_contacts:
            cache_contacts(all_contacts)
        
        timestamp = datetime.utcnow().isoformat()
        contacts_count = len(all_contacts)
        
        logger.info(f"Cache refresh completed. Cached {contacts_count} contacts.")
        
        return RefreshCacheResponse(
            success=True,
            message=f"Successfully refreshed {contacts_count} contacts",
            contacts_refreshed=contacts_count,
            timestamp=timestamp
        )
        
    except Exception as e:
        logger.error(f"Error refreshing contacts cache: {e}")
        return RefreshCacheResponse(
            success=False,
            message=f"Failed to refresh contacts cache: {str(e)}",
            contacts_refreshed=0,
            timestamp=datetime.utcnow().isoformat()
        )


def get_admin_contact() -> Optional[GoogleContact]:
    """
    Get the admin contact configured in config.json.
    
    Returns:
        GoogleContact: The admin contact, or None if not found
    """
    try:
        config = get_config()
        admin_email = config.get('contacts', {}).get('admin_email')
        
        if not admin_email:
            logger.warning("No admin email configured in config.json")
            return None
        
        # Try to get from cache first
        contact_data = get_cached_contact_by_email(admin_email)
        
        if contact_data:
            logger.debug(f"Found admin contact in cache: {admin_email}")
            return _convert_contact_data(contact_data)
        
        logger.info(f"Admin contact not found in cache for {admin_email}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting admin contact: {e}")
        return None


def get_contact_by_email(email: str) -> Optional[GoogleContact]:
    """
    Get a contact by email address.
    
    Args:
        email: The email address to search for
        
    Returns:
        GoogleContact: The contact, or None if not found
    """
    try:
        # Try to get from cache first
        contact_data = get_cached_contact_by_email(email)
        
        if contact_data:
            logger.debug(f"Found contact in cache: {email}")
            return _convert_contact_data(contact_data)
        
        logger.info(f"Contact not found in cache for {email}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting contact by email {email}: {e}")
        return None


def list_all_contacts() -> ContactsListResponse:
    """
    List all contacts from cache.
    
    Returns:
        ContactsListResponse: List of all contacts
    """
    try:
        # Get all contacts from cache
        cached_contacts = get_all_cached_contacts()
        
        # Convert to GoogleContact models
        contacts = []
        for contact_data in cached_contacts:
            try:
                contact = _convert_contact_data(contact_data)
                contacts.append(contact)
            except Exception as e:
                logger.warning(f"Error converting contact data: {e}")
                continue
        
        logger.debug(f"Retrieved {len(contacts)} contacts from cache")
        
        return ContactsListResponse(
            contacts=contacts,
            total_items=len(contacts)
        )
        
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        return ContactsListResponse(
            contacts=[],
            total_items=0
        )


def get_contacts_cache_status() -> Dict[str, Any]:
    """
    Get the status of the contacts cache.
    
    Returns:
        Dict containing cache status information
    """
    try:
        stats = get_cache_stats()
        return {
            'cache_initialized': True,
            'stats': stats
        }
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return {
            'cache_initialized': False,
            'error': str(e)
        }


def create_contact(contact_request: CreateContactRequest) -> CreateContactResponse:
    """
    Create a new contact using the Google People API.
    
    Args:
        contact_request: The contact data to create
        
    Returns:
        CreateContactResponse: Status and data of the created contact
    """
    try:
        logger.info(f"Creating new contact: {contact_request.display_name}")
        
        # Get People API service
        service = get_people_service()
        
        # Build the contact data for Google People API
        contact_body = {}
        
        # Add names if provided
        if any([contact_request.display_name, contact_request.given_name, 
                contact_request.family_name, contact_request.middle_name]):
            names = [{}]
            if contact_request.display_name:
                names[0]['displayName'] = contact_request.display_name
            if contact_request.given_name:
                names[0]['givenName'] = contact_request.given_name
            if contact_request.family_name:
                names[0]['familyName'] = contact_request.family_name
            if contact_request.middle_name:
                names[0]['middleName'] = contact_request.middle_name
            contact_body['names'] = names
        
        # Add email addresses if provided
        if contact_request.email_addresses:
            email_addresses = []
            for email in contact_request.email_addresses:
                email_data = {'value': email.value}
                if email.type:
                    email_data['type'] = email.type
                email_addresses.append(email_data)
            contact_body['emailAddresses'] = email_addresses
        
        # Add phone numbers if provided
        if contact_request.phone_numbers:
            phone_numbers = []
            for phone in contact_request.phone_numbers:
                phone_data = {'value': phone.value}
                if phone.type:
                    phone_data['type'] = phone.type
                phone_numbers.append(phone_data)
            contact_body['phoneNumbers'] = phone_numbers
        
        # Add addresses if provided
        if contact_request.addresses:
            addresses = []
            for address in contact_request.addresses:
                address_data = {}
                if address.formatted_value:
                    address_data['formattedValue'] = address.formatted_value
                if address.street_address:
                    address_data['streetAddress'] = address.street_address
                if address.city:
                    address_data['city'] = address.city
                if address.region:
                    address_data['region'] = address.region
                if address.postal_code:
                    address_data['postalCode'] = address.postal_code
                if address.country:
                    address_data['country'] = address.country
                if address.type:
                    address_data['type'] = address.type
                addresses.append(address_data)
            contact_body['addresses'] = addresses
        
        # Add organizations if provided
        if contact_request.organizations:
            contact_body['organizations'] = contact_request.organizations
        
        # Add notes if provided (stored as biography)
        if contact_request.notes:
            contact_body['biographies'] = [{'value': contact_request.notes, 'contentType': 'TEXT_PLAIN'}]
        
        # Create the contact via People API
        result = service.people().createContact(body=contact_body).execute()
        
        # Convert the result to our GoogleContact model
        created_contact = _convert_contact_data(result)
        
        # Cache the new contact
        cache_contact(result)
        
        logger.info(f"Successfully created contact: {result.get('resourceName')}")
        
        return CreateContactResponse(
            success=True,
            message="Contact created successfully",
            contact=created_contact,
            resource_name=result.get('resourceName')
        )
        
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        return CreateContactResponse(
            success=False,
            message=f"Failed to create contact: {str(e)}",
            contact=None,
            resource_name=None
        )


def resolve_contact_identifier(contact_identifier: str) -> str:
    """
    Resolve a contact identifier (name, email, or resource name) to a resource name.
    
    Args:
        contact_identifier: Contact identifier (resource name, exact name, or email)
        
    Returns:
        str: Resource name (people/xxx)
        
    Raises:
        ValueError: If contact cannot be found
    """
    # If it's already a resource name, return as-is
    if contact_identifier.startswith('people/'):
        return contact_identifier
    
    # Try to find contact by exact name or email
    try:
        all_contacts = list_all_contacts()
        
        for contact in all_contacts.contacts:
            # Check email addresses
            if contact.email_addresses:
                for email in contact.email_addresses:
                    if email.value.lower() == contact_identifier.lower():
                        return contact.resource_name
            
            # Check exact name matches
            if contact.names:
                for name in contact.names:
                    # Check display name
                    if name.display_name and name.display_name.lower() == contact_identifier.lower():
                        return contact.resource_name
                    # Check full name (given + family)
                    if name.given_name and name.family_name:
                        full_name = f"{name.given_name} {name.family_name}"
                        if full_name.lower() == contact_identifier.lower():
                            return contact.resource_name
        
        raise ValueError(f"Contact not found: {contact_identifier}")
        
    except Exception as e:
        logger.error(f"Error resolving contact identifier '{contact_identifier}': {e}")
        raise ValueError(f"Could not resolve contact: {contact_identifier}")


def search_contacts(search_request: SearchContactsRequest) -> ContactResponse:
    """
    Search contacts by query string (name, email, phone, etc.).
    Uses both Google's searchContacts API and local fuzzy matching.
    
    Args:
        search_request: The search parameters
        
    Returns:
        ContactResponse: Search results
    """
    try:
        logger.info(f"Searching contacts with query: {search_request.query}")
        
        # Get People API service
        service = get_people_service()
        
        contacts = []
        
        # First, try Google's searchContacts API
        try:
            result = service.people().searchContacts(
                query=search_request.query,
                pageSize=search_request.max_results,
                readMask='names,emailAddresses,phoneNumbers,addresses,organizations,biographies,photos,metadata'
            ).execute()
            
            if 'results' in result:
                for search_result in result['results']:
                    if 'person' in search_result:
                        contact = _convert_contact_data(search_result['person'])
                        contacts.append(contact)
        except Exception as google_api_error:
            logger.warning(f"Google searchContacts API failed: {google_api_error}")
        
        # If we didn't find enough results, also do local fuzzy matching
        if len(contacts) < search_request.max_results:
            try:
                all_contacts = list_all_contacts()
                query_lower = search_request.query.lower()
                
                # Search through all contacts for partial matches
                for contact in all_contacts.contacts:
                    # Skip if we already have this contact from the API search
                    if any(c.resource_name == contact.resource_name for c in contacts):
                        continue
                    
                    # Check names
                    name_match = False
                    if contact.names:
                        for name in contact.names:
                            if (name.display_name and query_lower in name.display_name.lower()) or \
                               (name.given_name and query_lower in name.given_name.lower()) or \
                               (name.family_name and query_lower in name.family_name.lower()) or \
                               (name.given_name and name.family_name and 
                                query_lower in f"{name.given_name} {name.family_name}".lower()):
                                name_match = True
                                break
                    
                    # Check email addresses
                    email_match = False
                    if contact.email_addresses:
                        for email in contact.email_addresses:
                            if query_lower in email.value.lower():
                                email_match = True
                                break
                    
                    # Check phone numbers
                    phone_match = False
                    if contact.phone_numbers:
                        for phone in contact.phone_numbers:
                            if query_lower in phone.value:
                                phone_match = True
                                break
                    
                    # Check biographies/notes
                    biography_match = False
                    if contact.biographies:
                        for biography in contact.biographies:
                            if isinstance(biography, dict) and 'value' in biography:
                                if query_lower in biography['value'].lower():
                                    biography_match = True
                                    break
                    
                    # If any field matches, add to results
                    if name_match or email_match or phone_match or biography_match:
                        contacts.append(contact)
                        if len(contacts) >= search_request.max_results:
                            break
                            
            except Exception as local_search_error:
                logger.warning(f"Local contact search failed: {local_search_error}")
        
        logger.info(f"Found {len(contacts)} contacts matching query")
        
        return ContactResponse(
            success=True,
            message=f"Found {len(contacts)} contacts matching query",
            contacts=contacts
        )
        
    except Exception as e:
        logger.error(f"Error searching contacts: {e}")
        return ContactResponse(
            success=False,
            message=f"Failed to search contacts: {str(e)}",
            contacts=[]
        )


def update_contact(update_request: UpdateContactRequest) -> ContactResponse:
    """
    Update an existing contact using the Google People API.
    
    Args:
        update_request: The contact data to update
        
    Returns:
        ContactResponse: Status and updated contact data
    """
    try:
        logger.info(f"Updating contact: {update_request.contact_identifier}")
        
        # Resolve the contact identifier to a resource name
        resource_name = resolve_contact_identifier(update_request.contact_identifier)
        
        # Get People API service
        service = get_people_service()
        
        # First, get the current contact to merge with updates
        current_contact = service.people().get(
            resourceName=resource_name,
            personFields='names,emailAddresses,phoneNumbers,addresses,organizations,biographies,photos,metadata'
        ).execute()
        
        # Build the update data
        contact_body = {}
        
        # Update names if provided
        if any([update_request.display_name, update_request.given_name, 
                update_request.family_name, update_request.middle_name]):
            names = [{}]
            if update_request.display_name:
                names[0]['displayName'] = update_request.display_name
            if update_request.given_name:
                names[0]['givenName'] = update_request.given_name
            if update_request.family_name:
                names[0]['familyName'] = update_request.family_name
            if update_request.middle_name:
                names[0]['middleName'] = update_request.middle_name
            contact_body['names'] = names
        
        # Update email addresses if provided
        if update_request.email_addresses is not None:
            email_addresses = []
            for email in update_request.email_addresses:
                email_data = {'value': email.value}
                if email.type:
                    email_data['type'] = email.type
                email_addresses.append(email_data)
            contact_body['emailAddresses'] = email_addresses
        
        # Update phone numbers if provided
        if update_request.phone_numbers is not None:
            phone_numbers = []
            for phone in update_request.phone_numbers:
                phone_data = {'value': phone.value}
                if phone.type:
                    phone_data['type'] = phone.type
                phone_numbers.append(phone_data)
            contact_body['phoneNumbers'] = phone_numbers
        
        # Update addresses if provided
        if update_request.addresses is not None:
            addresses = []
            for address in update_request.addresses:
                address_data = {}
                if address.formatted_value:
                    address_data['formattedValue'] = address.formatted_value
                if address.street_address:
                    address_data['streetAddress'] = address.street_address
                if address.city:
                    address_data['city'] = address.city
                if address.region:
                    address_data['region'] = address.region
                if address.postal_code:
                    address_data['postalCode'] = address.postal_code
                if address.country:
                    address_data['country'] = address.country
                if address.type:
                    address_data['type'] = address.type
                addresses.append(address_data)
            contact_body['addresses'] = addresses
        
        # Update organizations if provided
        if update_request.organizations is not None:
            contact_body['organizations'] = update_request.organizations
        
        # Update notes if provided
        if update_request.notes is not None:
            contact_body['biographies'] = [{'value': update_request.notes, 'contentType': 'TEXT_PLAIN'}]
        
        # Add etag for safe updates
        contact_body['etag'] = current_contact.get('etag')
        
        # Build the update fields list (excluding etag)
        update_fields = [field for field in contact_body.keys() if field != 'etag']
        
        # Update the contact via People API
        result = service.people().updateContact(
            resourceName=resource_name,
            body=contact_body,
            updatePersonFields=','.join(update_fields)
        ).execute()
        
        # Convert the result to our GoogleContact model
        updated_contact = _convert_contact_data(result)
        
        # Update cache
        cache_contact(result)
        
        logger.info(f"Successfully updated contact: {resource_name}")
        
        return ContactResponse(
            success=True,
            message="Contact updated successfully",
            contact=updated_contact,
            resource_name=resource_name
        )
        
    except ValueError as ve:
        logger.error(f"Contact resolution error: {ve}")
        return ContactResponse(
            success=False,
            message=str(ve),
            contact=None,
            resource_name=None
        )
    except Exception as e:
        logger.error(f"Error updating contact: {e}")
        return ContactResponse(
            success=False,
            message=f"Failed to update contact: {str(e)}",
            contact=None,
            resource_name=None
        )


def delete_contact(delete_request: DeleteContactRequest) -> ContactResponse:
    """
    Delete a contact using the Google People API.
    
    Args:
        delete_request: The contact deletion request
        
    Returns:
        ContactResponse: Status of the deletion
    """
    try:
        logger.info(f"Deleting contact: {delete_request.contact_identifier}")
        
        # Resolve the contact identifier to a resource name
        resource_name = resolve_contact_identifier(delete_request.contact_identifier)
        
        # Get People API service
        service = get_people_service()
        
        # Delete the contact via People API
        service.people().deleteContact(resourceName=resource_name).execute()
        
        # Remove from cache if it exists
        # Note: We could implement cache removal, but for now just log success
        
        logger.info(f"Successfully deleted contact: {resource_name}")
        
        return ContactResponse(
            success=True,
            message="Contact deleted successfully",
            resource_name=resource_name
        )
        
    except ValueError as ve:
        logger.error(f"Contact resolution error: {ve}")
        return ContactResponse(
            success=False,
            message=str(ve),
            resource_name=None
        )
    except Exception as e:
        logger.error(f"Error deleting contact: {e}")
        return ContactResponse(
            success=False,
            message=f"Failed to delete contact: {str(e)}",
            resource_name=None
        )
