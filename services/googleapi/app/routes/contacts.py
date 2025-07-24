"""
Google Contacts API Routes for FastAPI

This module defines the API endpoints for interacting with Google Contacts via Google's People API.
It provides endpoints for retrieving contacts, managing cache, and getting admin contact information.

Endpoints:
    - GET /admin: Get the admin contact configured in config.json.
    - GET /: List all contacts from cache.
    - GET /{email}: Get a specific contact by email address.
    - POST /cache/refresh: Refresh the contacts cache from Google API.
    - GET /cache/status: Get the status of the contacts cache.

All endpoints handle exceptions and return appropriate HTTP error responses.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional

from shared.models.googleapi import GoogleContact, ContactsListResponse, RefreshCacheResponse, CreateContactRequest, CreateContactResponse
from app.services.contacts.contacts import (
    get_admin_contact,
    get_contact_by_email,
    list_all_contacts,
    refresh_contacts_cache,
    get_contacts_cache_status,
    create_contact
)

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

router = APIRouter()


@router.get("/admin", response_model=GoogleContact)
async def get_admin_contact_endpoint():
    """
    Get the admin contact configured in config.json.
    
    Returns:
        GoogleContact: The admin contact information
        
    Raises:
        HTTPException: 404 if admin contact not found, 500 for other errors
    """
    try:
        logger.info("Retrieving admin contact")
        
        admin_contact = get_admin_contact()
        if not admin_contact:
            logger.warning("Admin contact not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin contact not found. Check configuration and cache."
            )
        
        logger.debug(f"Retrieved admin contact: {admin_contact.names[0].display_name if admin_contact.names else 'Unknown'}")
        return admin_contact
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving admin contact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve admin contact: {str(e)}"
        )


@router.get("/", response_model=ContactsListResponse)
async def list_contacts_endpoint():
    """
    List all contacts from cache.
    
    Returns:
        ContactsListResponse: List of all contacts
        
    Raises:
        HTTPException: 500 for errors
    """
    try:
        logger.info("Listing all contacts from cache")
        
        contacts_response = list_all_contacts()
        
        logger.debug(f"Retrieved {len(contacts_response.contacts)} contacts")
        return contacts_response
        
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list contacts: {str(e)}"
        )


@router.get("/{email}", response_model=GoogleContact)
async def get_contact_by_email_endpoint(email: str):
    """
    Get a specific contact by email address.
    
    Args:
        email: The email address to search for
        
    Returns:
        GoogleContact: The contact information
        
    Raises:
        HTTPException: 404 if contact not found, 500 for other errors
    """
    try:
        logger.info(f"Retrieving contact by email: {email}")
        
        contact = get_contact_by_email(email)
        if not contact:
            logger.warning(f"Contact not found for email: {email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact not found for email: {email}"
            )
        
        logger.debug(f"Retrieved contact: {contact.names[0].display_name if contact.names else 'Unknown'}")
        return contact
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving contact by email {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve contact: {str(e)}"
        )


@router.post("/cache/refresh", response_model=RefreshCacheResponse)
async def refresh_cache_endpoint():
    """
    Refresh the contacts cache from Google API.
    
    Returns:
        RefreshCacheResponse: Status of the cache refresh operation
        
    Raises:
        HTTPException: 500 for errors
    """
    try:
        logger.info("Starting contacts cache refresh")
        
        response = refresh_contacts_cache()
        
        if response.success:
            logger.info(f"Cache refresh completed: {response.message}")
        else:
            logger.error(f"Cache refresh failed: {response.message}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh cache: {str(e)}"
        )


@router.get("/cache/status")
async def get_cache_status_endpoint():
    """
    Get the status of the contacts cache.
    
    Returns:
        Dict containing cache status information
        
    Raises:
        HTTPException: 500 for errors
    """
    try:
        logger.info("Retrieving cache status")
        
        status_info = get_contacts_cache_status()
        
        logger.debug(f"Cache status: {status_info}")
        return status_info
        
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache status: {str(e)}"
        )


@router.post("/", response_model=CreateContactResponse)
async def create_contact_endpoint(request: CreateContactRequest):
    """
    Create a new contact in Google Contacts.
    
    Args:
        request: The contact creation request data
        
    Returns:
        CreateContactResponse: Status and data of the created contact
        
    Raises:
        HTTPException: 400 for validation errors, 500 for other errors
    """
    try:
        logger.info(f"Creating contact: {request.display_name}")
        
        # Validate that at least some contact information is provided
        if not any([
            request.display_name, request.given_name, request.family_name,
            request.email_addresses, request.phone_numbers
        ]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of display_name, given_name, family_name, email_addresses, or phone_numbers must be provided"
            )
        
        response = create_contact(request)
        
        if response.success:
            logger.info(f"Contact created successfully: {response.resource_name}")
        else:
            logger.error(f"Contact creation failed: {response.message}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contact: {str(e)}"
        )
