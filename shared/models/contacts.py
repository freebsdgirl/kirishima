"""
This module defines Pydantic models for managing contact data.
The models include:
- `ContactCreate`: Represents the data required to create a new contact, including aliases, additional fields, and optional notes.
- `Contact`: Represents a complete contact entry with a unique identifier, aliases, additional fields, and optional notes.
Classes:
    - ContactCreate: A Pydantic model for creating a new contact.
    - Contact: A Pydantic model for representing a contact entry.
Usage:
    These models can be used for data validation and serialization/deserialization
    when working with contact-related data in an application.
Examples:
    Example data for each model is provided in the `json_schema_extra` attribute
    for reference when constructing or validating instances.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    """
    Represents the data required to create a new contact.
    
    Captures the necessary details for creating a contact entry,
    including a list of aliases, additional fields as key-value pairs,
    and optional notes.
    
    Attributes:
        aliases (List[str]): A list of alternative names or identifiers for the contact.
        fields (List[Dict[str, Any]]): A list of key-value pairs containing additional contact information.
        notes (Optional[str]): Optional notes or comments about the contact.
    """
    aliases: List[str] = Field(..., description="A list of alternative names or identifiers for the contact.")
    fields: List[Dict[str, Any]] = Field(..., description="A list of key-value pairs containing additional contact information.")
    notes: Optional[str] = Field(None, description="Optional notes or comments about the contact.")
    class Config:
        json_schema_extra = {
            "example": {
                "aliases": ["John Doe", "JD"],
                "fields": [
                    {"key": "email", "value": "john@example.com"},
                    {"key": "phone", "value": "+1234567890"}
                ],
                "notes": "Preferred contact during business hours."
            }
        }


class Contact(BaseModel):
    """
    Represents a contact entry with all its details.
    
    Includes the unique identifier for the contact along with its aliases,
    additional fields, and optional notes. This model is used when returning
    contact data to the client.
    
    Attributes:
        id (str): The unique identifier for the contact.
        aliases (List[str]): A list of alternative names or identifiers for the contact.
        fields (List[Dict[str, Any]]): A list of key-value pairs containing additional contact information.
        notes (Optional[str]): Optional notes or comments about the contact.
    """
    id: str = Field(..., description="The unique identifier for the contact.")
    aliases: List[str] = Field(..., description="A list of alternative names or identifiers for the contact.")
    fields: List[Dict[str, Any]] = Field(..., description="A list of key-value pairs containing additional contact information.")
    notes: Optional[str] = Field(None, description="Optional notes or comments about the contact.")
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "aliases": ["John Doe", "JD"],
                "fields": [
                    {"key": "email", "value": "john@example.com"},
                    {"key": "phone", "value": "+1234567890"}
                ],
                "notes": "Preferred contact during business hours."
            }
        }