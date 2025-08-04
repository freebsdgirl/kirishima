"""
Contacts-specific models for GoogleAPI service.
Contains request and response models for Google Contacts operations.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ContactName(BaseModel):
    """
    Represents a contact's name information.
    """
    display_name: Optional[str] = Field(None, description="The contact's display name")
    given_name: Optional[str] = Field(None, description="The contact's first name")
    family_name: Optional[str] = Field(None, description="The contact's last name")
    middle_name: Optional[str] = Field(None, description="The contact's middle name")


class ContactEmail(BaseModel):
    """
    Represents a contact's email address.
    """
    value: str = Field(..., description="The email address")
    type: Optional[str] = Field(None, description="The type of email (home, work, etc.)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Email metadata")


class ContactPhoneNumber(BaseModel):
    """
    Represents a contact's phone number.
    """
    value: str = Field(..., description="The phone number")
    type: Optional[str] = Field(None, description="The type of phone number (home, work, mobile, etc.)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Phone number metadata")


class ContactAddress(BaseModel):
    """
    Represents a contact's address.
    """
    formatted_value: Optional[str] = Field(None, description="The formatted address")
    street_address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City")
    region: Optional[str] = Field(None, description="State/region")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    country: Optional[str] = Field(None, description="Country")
    type: Optional[str] = Field(None, description="The type of address (home, work, etc.)")


class GoogleContact(BaseModel):
    """
    Represents a Google contact with all available information.
    """
    resource_name: str = Field(..., description="The contact's resource name (ID)")
    etag: Optional[str] = Field(None, description="The contact's etag for versioning")
    names: Optional[List[ContactName]] = Field(None, description="The contact's names")
    email_addresses: Optional[List[ContactEmail]] = Field(None, description="The contact's email addresses")
    phone_numbers: Optional[List[ContactPhoneNumber]] = Field(None, description="The contact's phone numbers")
    addresses: Optional[List[ContactAddress]] = Field(None, description="The contact's addresses")
    organizations: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's organizations")
    birthdays: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's birthdays")
    biographies: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's biographies/notes")
    photos: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's photos")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Contact metadata")
    created_time: Optional[str] = Field(None, description="When the contact was created")
    modified_time: Optional[str] = Field(None, description="When the contact was last modified")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "resource_name": "people/c12345",
                    "names": [
                        {
                            "display_name": "John Smith",
                            "given_name": "John",
                            "family_name": "Smith"
                        }
                    ],
                    "email_addresses": [
                        {
                            "value": "john.smith@example.com",
                            "type": "work"
                        }
                    ],
                    "phone_numbers": [
                        {
                            "value": "+1234567890",
                            "type": "mobile"
                        }
                    ]
                }
            ]
        }
    }


class ContactsListResponse(BaseModel):
    """
    Response model for listing contacts.
    """
    contacts: List[GoogleContact] = Field(..., description="List of contacts")
    next_page_token: Optional[str] = Field(None, description="Token for next page of results")
    total_items: Optional[int] = Field(None, description="Total number of contacts")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "contacts": [
                        {
                            "resource_name": "people/c12345",
                            "names": [{"display_name": "John Smith"}]
                        }
                    ],
                    "total_items": 1
                }
            ]
        }
    }


class RefreshCacheResponse(BaseModel):
    """
    Response model for cache refresh operations.
    """
    success: bool = Field(..., description="Whether the cache refresh was successful")
    message: str = Field(..., description="Status message")
    contacts_refreshed: int = Field(..., description="Number of contacts refreshed")
    timestamp: str = Field(..., description="Timestamp of the refresh operation")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Cache refreshed successfully",
                    "contacts_refreshed": 150,
                    "timestamp": "2025-07-24T10:30:00Z"
                }
            ]
        }
    }


class CreateContactRequest(BaseModel):
    """
    Request model for creating a new contact.
    """
    display_name: Optional[str] = Field(None, description="The contact's display name")
    given_name: Optional[str] = Field(None, description="The contact's first name")
    family_name: Optional[str] = Field(None, description="The contact's last name")
    middle_name: Optional[str] = Field(None, description="The contact's middle name")
    email_addresses: Optional[List[ContactEmail]] = Field(None, description="The contact's email addresses")
    phone_numbers: Optional[List[ContactPhoneNumber]] = Field(None, description="The contact's phone numbers")
    addresses: Optional[List[ContactAddress]] = Field(None, description="The contact's addresses")
    organizations: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's organizations")
    notes: Optional[str] = Field(None, description="Notes about the contact")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "display_name": "John Smith",
                    "given_name": "John",
                    "family_name": "Smith",
                    "email_addresses": [
                        {
                            "value": "john.smith@example.com",
                            "type": "work"
                        }
                    ],
                    "phone_numbers": [
                        {
                            "value": "+1234567890",
                            "type": "mobile"
                        }
                    ]
                }
            ]
        }
    }


class CreateContactResponse(BaseModel):
    """
    Response model for contact creation operations.
    """
    success: bool = Field(..., description="Whether the contact creation was successful")
    message: str = Field(..., description="Status message")
    contact: Optional[GoogleContact] = Field(None, description="The created contact data")
    resource_name: Optional[str] = Field(None, description="The resource name of the created contact")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Contact created successfully",
                    "contact": {
                        "resource_name": "people/c12345",
                        "names": [{"display_name": "John Doe"}]
                    },
                    "resource_name": "people/c12345"
                }
            ]
        }
    }


class SearchContactsRequest(BaseModel):
    """
    Request model for searching contacts by various fields.
    """
    query: str = Field(..., description="Search query for names, emails, phone numbers, or other fields")
    max_results: Optional[int] = Field(25, description="Maximum number of contacts to return")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "john smith",
                    "max_results": 10
                },
                {
                    "query": "john@example.com",
                    "max_results": 5
                }
            ]
        }
    }


class UpdateContactRequest(BaseModel):
    """
    Request model for updating an existing contact.
    """
    contact_identifier: str = Field(..., description="Contact identifier: resource name (people/xxx), exact name, or email address")
    display_name: Optional[str] = Field(None, description="The contact's display name")
    given_name: Optional[str] = Field(None, description="The contact's first name")
    family_name: Optional[str] = Field(None, description="The contact's last name")
    middle_name: Optional[str] = Field(None, description="The contact's middle name")
    email_addresses: Optional[List[ContactEmail]] = Field(None, description="The contact's email addresses")
    phone_numbers: Optional[List[ContactPhoneNumber]] = Field(None, description="The contact's phone numbers")
    addresses: Optional[List[ContactAddress]] = Field(None, description="The contact's addresses")
    organizations: Optional[List[Dict[str, Any]]] = Field(None, description="The contact's organizations")
    notes: Optional[str] = Field(None, description="Notes about the contact")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "contact_identifier": "John Smith",
                    "display_name": "John Smith Jr.",
                    "email_addresses": [
                        {
                            "value": "john.smith@example.com",
                            "type": "work"
                        }
                    ],
                    "phone_numbers": [
                        {
                            "value": "+1234567890",
                            "type": "mobile"
                        }
                    ]
                },
                {
                    "contact_identifier": "john@example.com",
                    "display_name": "John Smith"
                }
            ]
        }
    }


class DeleteContactRequest(BaseModel):
    """
    Request model for deleting a contact.
    """
    contact_identifier: str = Field(..., description="Contact identifier: resource name (people/xxx), exact name, or email address")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "contact_identifier": "John Smith"
                },
                {
                    "contact_identifier": "john@example.com"
                }
            ]
        }
    }


class ContactResponse(BaseModel):
    """
    Response model for contact operations.
    """
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    contact: Optional[GoogleContact] = Field(None, description="The contact data (for single contact operations)")
    contacts: Optional[List[GoogleContact]] = Field(None, description="List of contacts (for search/list operations)")
    resource_name: Optional[str] = Field(None, description="The resource name of the affected contact")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Contact updated successfully",
                    "contact": {
                        "resource_name": "people/c12345",
                        "names": [{"display_name": "John Smith"}]
                    },
                    "resource_name": "people/c12345"
                },
                {
                    "success": True,
                    "message": "Found 3 contacts matching query",
                    "contacts": [
                        {
                            "resource_name": "people/c12345",
                            "names": [{"display_name": "John Smith"}]
                        }
                    ]
                }
            ]
        }
    } 