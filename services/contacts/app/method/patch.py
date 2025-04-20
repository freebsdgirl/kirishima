"""
This module provides an endpoint for partially updating an existing contact by ID.

The `patch_contact` function allows updating specific fields of a contact, such as notes, aliases, 
and custom fields. It ensures that only the provided fields in the request are updated, leaving 
other fields untouched. For custom fields, it supports adding, updating, or deleting fields based 
on the provided data.

Functions:
- patch_contact: Handles PATCH requests to update a contact by ID.

Dependencies:
- FastAPI for API routing and HTTP exception handling.
- SQLite3 for database operations.
- Shared utilities for logging, database connection, and alias uniqueness checks.
- Models for contact data validation and serialization.

Logging:
- Logs debug information for incoming requests and successful updates.
- Logs errors for missing contacts or database issues.

Raises:
- HTTPException with status 404 if the contact is not found.
- HTTPException with status 500 for database-related errors.
"""

from app.util import get_db_connection, check_admin_alias_uniqueness

from shared.models.contacts import Contact, ContactUpdate

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

import sqlite3

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.patch("/contact/{contact_id}", response_model=Contact)
def patch_contact(contact_id: str, contact: ContactUpdate) -> dict:
    """
    Partially update an existing contact by ID.
    Allows updating notes, aliases, and fields for a specific contact.
    Only updates fields provided in the request. For fields, only updates or adds the specified keys, leaving others untouched.
    """
    logger.debug(f"/contact/{{contact_id}} Request:\n{contact.model_dump_json(indent=4)}")

    try:
        with get_db_connection() as conn:
            if contact.aliases is not None:
                check_admin_alias_uniqueness(conn, contact_id, contact.aliases)
            cursor = conn.cursor()
            cursor.execute("SELECT notes FROM contacts WHERE id = ?", (contact_id,))
            if not cursor.fetchone():
                logger.error(f"Contact {contact_id} not found for patch.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contact not found"
                )

            # Update notes if provided
            if contact.notes is not None:
                cursor.execute("UPDATE contacts SET notes = ? WHERE id = ?", (contact.notes, contact_id))

            # Replace aliases if provided
            if contact.aliases is not None:
                cursor.execute("DELETE FROM aliases WHERE contact_id = ?", (contact_id,))
                for alias in contact.aliases:
                    cursor.execute("INSERT INTO aliases (contact_id, alias) VALUES (?, ?)", (contact_id, alias))

            # Update/add/delete fields by key if provided (empty string deletes field)
            if contact.fields is not None:
                for field in contact.fields:
                    key = field.get("key")
                    value = field.get("value")
                    # Check if field with this key exists for this contact
                    cursor.execute("SELECT id FROM fields WHERE contact_id = ? AND key = ?", (contact_id, key))
                    row = cursor.fetchone()
                    if value == "":
                        # Delete field if value is empty string
                        if row:
                            cursor.execute("DELETE FROM fields WHERE id = ?", (row[0],))
                            logger.info(f"Deleted field '{key}' for contact {contact_id}")
                    elif row:
                        cursor.execute("UPDATE fields SET value = ? WHERE id = ?", (value, row[0]))
                        logger.info(f"Updated field '{key}' for contact {contact_id}")
                    else:
                        cursor.execute("INSERT INTO fields (contact_id, key, value) VALUES (?, ?, ?)", (contact_id, key, value))
                        logger.info(f"Added field '{key}' for contact {contact_id}")

            conn.commit()

            # Fetch the full contact object to return
            cursor.execute("SELECT notes FROM contacts WHERE id = ?", (contact_id,))
            notes_row = cursor.fetchone()
            notes = notes_row[0] if notes_row else None

            cursor.execute("SELECT alias FROM aliases WHERE contact_id = ?", (contact_id,))
            aliases = [row[0] for row in cursor.fetchall()]

            cursor.execute("SELECT key, value FROM fields WHERE contact_id = ?", (contact_id,))
            fields = [{"key": row[0], "value": row[1]} for row in cursor.fetchall()]

            result = {
                "id": contact_id,
                "aliases": aliases,
                "fields": fields,
                "notes": notes
            }

    except sqlite3.Error as e:
        logger.error(f"Error patching contact {contact_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to patch contact due to a database error"
        )

    logger.debug(f"Contact {contact_id} patched successfully.")

    return result