"""
This module defines an API endpoint for replacing an existing contact with new information.

The endpoint is implemented as a PUT request to `/contact/{contact_id}` and allows for the complete
replacement of a contact's notes, aliases, and fields. It ensures that the contact exists before
performing the replacement and validates the uniqueness of admin aliases. If the contact does not
exist, a 404 HTTP error is raised. If a database error occurs during the operation, a 500 HTTP error
is raised.

Functions:
    replace_contact(contact_id: str, contact: ContactCreate) -> dict:
        Replaces an existing contact with new information, ensuring the contact exists and
        validating alias uniqueness. Returns the updated contact information or raises an
        HTTP exception in case of errors.

Dependencies:
    - FastAPI for routing and HTTP exception handling.
    - SQLite3 for database operations.
    - Shared utilities for logging, database connection, and alias uniqueness validation.
    - Models for contact creation and representation.
"""

from app.util import get_db_connection, check_admin_alias_uniqueness

from shared.models.contacts import ContactCreate, Contact

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

import sqlite3

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.put("/contact/{contact_id}", response_model=Contact)
def replace_contact(contact_id: str, contact: ContactCreate) -> dict:
    """
    Replace an existing contact with new information.

    Completely replaces the contact's notes, aliases, and fields with the provided data.
    Verifies the contact exists before performing the replacement. Raises an HTTP 404 error
    if the contact is not found, or an HTTP 500 error if a database error occurs.
    """
    logger.debug(f"/contact/{contact_id} Request:\n{contact.model_dump_json(indent=4)}")

    try:
        with get_db_connection() as conn:
            check_admin_alias_uniqueness(conn, contact_id, contact.aliases)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM contacts WHERE id = ?", (contact_id,))

            if not cursor.fetchone():
                logger.warning(f"Contact {contact_id} not found for replacement.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contact not found"
                )

            cursor.execute("UPDATE contacts SET notes = ? WHERE id = ?", (contact.notes, contact_id))
            cursor.execute("DELETE FROM aliases WHERE contact_id = ?", (contact_id,))
            cursor.execute("DELETE FROM fields WHERE contact_id = ?", (contact_id,))

            for alias in contact.aliases:
                cursor.execute("INSERT INTO aliases (contact_id, alias) VALUES (?, ?)", (contact_id, alias))

            # Insert top-level fields if present
            for field_name in ["imessage", "discord", "discord_id", "email"]:
                value = getattr(contact, field_name, None)
                if value is not None:
                    cursor.execute(
                        "INSERT INTO fields (contact_id, key, value) VALUES (?, ?, ?)",
                        (contact_id, field_name, value)
                    )

            conn.commit()

            # Fetch the full contact object to return
            cursor.execute("SELECT notes FROM contacts WHERE id = ?", (contact_id,))
            notes_row = cursor.fetchone()
            notes = notes_row[0] if notes_row else None

            cursor.execute("SELECT alias FROM aliases WHERE contact_id = ?", (contact_id,))
            aliases = [row[0] for row in cursor.fetchall()]

            cursor.execute("SELECT key, value FROM fields WHERE contact_id = ?", (contact_id,))
            fields_dict = {row[0]: row[1] for row in cursor.fetchall()}

            result = {
                "id": contact_id,
                "aliases": aliases,
                "imessage": fields_dict.get("imessage"),
                "discord": fields_dict.get("discord"),
                "discord_id": fields_dict.get("discord_id"),
                "email": fields_dict.get("email"),
                "notes": notes
            }

    except sqlite3.Error as e:
        logger.error(f"Error replacing contact {contact_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to replace contact due to a database error"
        )

    logger.debug(f"Contact {contact_id} replaced successfully.")

    return result