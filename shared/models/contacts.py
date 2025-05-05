"""
This module defines Pydantic models for managing contact data.
The models include:
- `ContactCreate`: Represents the data required to create a new contact.
- `Contact`: Represents a contact entry with all its details, including a unique identifier.
- `ContactUpdate`: Represents a partial update for a contact entry, allowing modifications to specific fields.
Each model includes attributes with detailed descriptions and example data for better understanding and usage.
Classes:
    - ContactCreate: Captures the necessary details for creating a contact entry.
    - Contact: Represents a complete contact entry with all its details.
    - ContactUpdate: Allows partial updates to a contact entry.
    - aliases (List[str]): A list of alternative names or identifiers for the contact.
    - fields (List[Dict[str, Any]]): A list of key-value pairs containing additional contact information.
    - notes (Optional[str]): Optional notes or comments about the contact.
    - id (str): The unique identifier for the contact (specific to the `Contact` model).
Example Usage:
    - Creating a new contact using `ContactCreate`.
    - Retrieving a contact entry using `Contact`.
    - Updating specific fields of a contact using `ContactUpdate`.
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
    aliases: List[str]                      = Field(..., description="A list of alternative names or identifiers for the contact.")
    fields: List[Dict[str, Any]]            = Field(..., description="A list of key-value pairs containing additional contact information.")
    notes: Optional[str]                    = Field(None, description="Optional notes or comments about the contact.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "aliases": ["John Doe", "JD"],
                "fields": [
                    {"key": "email", "value": "john@doe.com"},
                    {"key": "phone", "value": "+1234567890"}
                ],
                "notes": "Preferred contact during business hours."
            }
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
        imessage (Optional[str]): Optional iMessage address for the contact.
        discord (Optional[str]): Optional Discord address for the contact.
        discord_id (Optional[str]): Optional Discord ID for the contact.
        email (Optional[str]): Optional email address for the contact.
        notes (Optional[str]): Optional notes or comments about the contact.
    """
    id: str                                 = Field(..., description="The unique identifier for the contact.")
    aliases: List[str]                      = Field(..., description="A list of alternative names or identifiers for the contact.")
    imessage: Optional[str]                 = Field(None, description="iMessage address for the contact.")
    discord: Optional[str]                  = Field(None, description="Discord address for the contact.")
    discord_id: Optional[str]               = Field(None, description="Discord ID for the contact.")
    email: Optional[str]                    = Field(None, description="Email address for the contact.")
    notes: Optional[str]                    = Field(None, description="Optional notes or comments about the contact.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "12345",
                "aliases": ["John Doe", "JD"],
                "imessage": "+1234567890",
                "discord": "john_doe#1234",
                "discord_id": "123456789012345678",
                "email": "test@test.com",
                "notes": "Preferred contact during business hours."
            }
        }
    }


class ContactUpdate(BaseModel):
    """
    Represents a partial update for a contact entry.
    
    This model allows updating specific fields of a contact without requiring all fields to be present.
    Useful for partial updates where only certain contact details need to be modified.
    
    Attributes:
        aliases (Optional[List[str]]): Optional list of alternative names or identifiers to update.
        fields (Optional[List[Dict[str, Any]]]): Optional list of key-value pairs to update contact information.
        notes (Optional[str]): Optional notes or comments to update for the contact.
    """
    aliases: Optional[List[str]]            = Field(None, description="A list of alternative names or identifiers for the contact.")
    fields: Optional[List[Dict[str, Any]]]  = Field(None, description="A list of key-value pairs containing additional contact information.")
    notes: Optional[str]                    = Field(None, description="Optional notes or comments about the contact.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "aliases": ["John Doe", "JD"],
                "fields": [
                    {"key": "email", "value": "john@doe.com"},
                    {"key": "phone", "value": "+1234567890"}
                ],
                "notes": "Preferred contact during business hours."
            }
        }
    }
