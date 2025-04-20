"""
This module provides an endpoint for creating a new contact in the contacts service.

The `/contact` endpoint allows clients to send a POST request with contact details, including notes, aliases, 
and additional fields. The contact is assigned a unique UUID and stored in the database. The module ensures 
that aliases are unique and logs the creation process.

Functions:
    add_contact(contact: ContactCreate) -> Contact:
        Handles the creation of a new contact, validates input, interacts with the database, and returns the 
        created contact object.

Dependencies:
    - app.util.get_db_connection: Provides a database connection.
    - app.util.check_admin_alias_uniqueness: Validates the uniqueness of aliases.
    - shared.models.contacts.ContactCreate: Input model for creating a contact.
    - shared.models.contacts.Contact: Output model for a contact.
    - shared.models.contacts.ContactUpdate: Model for updating a contact (not used in this module).
    - shared.log_config.get_logger: Configures logging for the module.
    - fastapi.APIRouter: Provides routing for the FastAPI application.
    - fastapi.HTTPException: Handles HTTP exceptions.
    - fastapi.status: Provides HTTP status codes.
    - sqlite3: Interacts with the SQLite database.
    - uuid: Generates unique identifiers for contacts.
"""

from app.util import get_db_connection, check_admin_alias_uniqueness

from shared.models.contacts import ContactCreate, Contact

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

import uuid
import sqlite3

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

@router.post("/contact", response_model=Contact)
def add_contact(contact: ContactCreate) -> Contact:
    """
    Create a new contact with the provided contact information.

    Creates a contact with a unique ID, storing the contact's notes, aliases, and additional fields
    in the database. Generates a unique UUID for the contact and logs the creation process.

    Args:
        contact (ContactCreate): The contact details to be created, including notes, aliases, and fields.

    Returns:
        Contact: The newly created contact.

    Raises:
        HTTPException: If there is a database error during contact creation, with a 500 Internal Server Error status.
    """
    contact_id = str(uuid.uuid4())
    logger.info(f"/contact Request:\n{contact.model_dump_json(indent=4)}")

    try:
        with get_db_connection() as conn:
            check_admin_alias_uniqueness(conn, None, contact.aliases)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO contacts (id, notes) VALUES (?, ?)", (contact_id, contact.notes))

            for alias in contact.aliases:
                cursor.execute("INSERT INTO aliases (contact_id, alias) VALUES (?, ?)", (contact_id, alias))

            for field in contact.fields:
                cursor.execute(
                    "INSERT INTO fields (contact_id, key, value) VALUES (?, ?, ?)",
                    (contact_id, field.get("key"), field.get("value"))
                )

            conn.commit()

            # Fetch the full contact object to return
            cursor.execute("SELECT notes FROM contacts WHERE id = ?", (contact_id,))
            notes_row = cursor.fetchone()
            notes = notes_row[0] if notes_row else None

            cursor.execute("SELECT alias FROM aliases WHERE contact_id = ?", (contact_id,))
            aliases = [row[0] for row in cursor.fetchall()]

            cursor.execute("SELECT key, value FROM fields WHERE contact_id = ?", (contact_id,))
            fields = [{"key": row[0], "value": row[1]} for row in cursor.fetchall()]

            result = Contact(
                id=contact_id,
                aliases=aliases,
                fields=fields,
                notes=notes
            )

    except sqlite3.Error as e:
        logger.error(f"Error creating contact {contact_id}: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contact due to a database error {e}"
        )

    logger.debug(f"Contact {contact_id} created successfully.")

    return result