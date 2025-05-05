"""
This module provides FastAPI endpoints for managing and retrieving contact information.
Endpoints:
    - GET /contacts: Retrieve a list of all contacts with their details.
    - GET /contacts/{contact_id}: Retrieve a specific contact by its unique identifier.
    - GET /search: Search for a contact by alias, field key-value pair, or general query.
Each endpoint interacts with a SQLite database to fetch contact details, including:
    - Contact ID
    - Notes
    - Aliases
    - Custom fields (key-value pairs)
Error Handling:
    - Returns HTTP 404 if a contact is not found.
    - Returns HTTP 400 for invalid search parameters.
    - Returns HTTP 500 for database-related errors.
Dependencies:
    - FastAPI for API routing and HTTP exception handling.
    - SQLite3 for database interactions.
    - Shared utilities for logging and database connection management.
Logging:
    - Logs debug information for each request and response.
    - Logs warnings for missing or invalid data.
    - Logs errors with stack traces for database issues.
"""

from app.util import get_db_connection

from shared.models.contacts import Contact

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

import sqlite3
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query

router = APIRouter()

@router.get("/contacts", response_model=list[Contact])
def list_contacts() -> list:
    """
    Retrieve and return a list of all contacts with their details.

    Fetches all contacts from the database, including their unique identifiers,
    notes, aliases, and additional fields. Returns a comprehensive list of contact
    information or raises an HTTP 500 error if a database error occurs.

    Returns:
        list: A list of contact dictionaries, each containing id, aliases, fields, and notes.

    Raises:
        HTTPException: If there is a database error during contact retrieval, with a 500 Internal Server Error status.
    """

    logger.debug("Listing all contacts.")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, notes FROM contacts")
            contact_rows = cursor.fetchall()

            result = []
            for contact_id, notes in contact_rows:
                cursor.execute("SELECT alias FROM aliases WHERE contact_id = ?", (contact_id,))
                aliases = [row[0] for row in cursor.fetchall()]

                # Gather all fields into a dict
                cursor.execute("SELECT key, value FROM fields WHERE contact_id = ?", (contact_id,))
                fields = {row[0]: row[1] for row in cursor.fetchall()}

                # Build the contact dict using .get() for optional fields
                contact = {
                    "id": contact_id,
                    "aliases": aliases,
                    "imessage": fields.get("imessage"),
                    "discord": fields.get("discord"),
                    "discord_id": fields.get("discord_id"),
                    "email": fields.get("email"),
                    "notes": notes
                }
                result.append(contact)

    except sqlite3.Error as e:
        logger.error(f"Error listing contacts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list contacts due to a database error: {e}"
        )

    return result


@router.get("/contact/{contact_id}", response_model=Contact)
def get_contact(contact_id: str) -> dict:
    """
    Retrieve a specific contact by its unique identifier.

    Fetches a single contact's details from the database, including its unique identifier,
    notes, aliases, and additional fields. Returns the contact information or raises
    an appropriate HTTP error if the contact is not found or a database error occurs.

    Args:
        contact_id (str): The unique identifier of the contact to retrieve.

    Returns:
        dict: A contact dictionary containing id, aliases, and notes.

    Raises:
        HTTPException: 404 if the contact is not found, 500 if a database error occurs.
    """

    logger.debug(f"Fetching contact by id: {contact_id}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Fetch notes (and implicitly check existence)
            cursor.execute("SELECT notes FROM contacts WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Contact not found: {contact_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contact not found"
                )
            notes = row[0] or ""

            # Fetch aliases
            cursor.execute(
                "SELECT alias FROM aliases WHERE contact_id = ?", (contact_id,)
            )
            aliases = [r[0] for r in cursor.fetchall()]

            # Fetch fields and unpack into dict
            cursor.execute(
                "SELECT key, value FROM fields WHERE contact_id = ?", (contact_id,)
            )
            fields = {r[0]: r[1] for r in cursor.fetchall()}

            result = {
                "id": contact_id,
                "aliases": aliases,
                "imessage": fields.get("imessage"),
                "discord": fields.get("discord"),
                "discord_id": fields.get("discord_id"),
                "email": fields.get("email"),
                "notes": notes
            }
            logger.debug(f"Contact retrieved: {result}")
            return result

    except sqlite3.Error as e:
        logger.error(f"Database error fetching contact {contact_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve contact due to database error: {e}"
        )


@router.get("/search", response_model=Contact)
def search_contacts(
    q: Optional[str] = Query(None, description="General search by alias or field value (exact match, case-insensitive)"),
    key: Optional[str] = Query(None, description="Field key to search on (e.g., platform)"),
    value: Optional[str] = Query(None, description="Field value to search for (e.g., sender_id)")
) -> dict:
    """
    Search contacts with an exact, case-insensitive match.
    """
    logger.debug(f"/search Request: q={q}, key={key}, value={value}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            contact_ids = set()

            if key is not None and value is not None:
                cursor.execute(
                    "SELECT contact_id FROM fields WHERE key = ? COLLATE NOCASE AND value = ? COLLATE NOCASE",
                    (key, value)
                )
                contact_ids.update(row[0] for row in cursor.fetchall())

            elif q is not None:
                cursor.execute("SELECT contact_id FROM aliases WHERE alias = ? COLLATE NOCASE", (q,))
                contact_ids.update(row[0] for row in cursor.fetchall())
                cursor.execute("SELECT contact_id FROM fields WHERE value = ? COLLATE NOCASE", (q,))
                contact_ids.update(row[0] for row in cursor.fetchall())

            else:
                logger.warning("Search parameters are missing.")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing search parameters."
                )

            if contact_ids:
                contact_id = list(contact_ids)[0]
                cursor.execute("SELECT notes FROM contacts WHERE id = ?", (contact_id,))
                notes_row = cursor.fetchone()
                notes = notes_row[0] if notes_row else ""

                cursor.execute("SELECT alias FROM aliases WHERE contact_id = ?", (contact_id,))
                aliases = [row[0] for row in cursor.fetchall()] 

                cursor.execute("SELECT key, value FROM fields WHERE contact_id = ?", (contact_id,))
                fields = {row[0]: row[1] for row in cursor.fetchall()}

                result = {
                    "id": contact_id,
                    "aliases": aliases,
                    "imessage": fields.get("imessage"),
                    "discord": fields.get("discord"),
                    "discord_id": fields.get("discord_id"),
                    "email": fields.get("email"),
                    "notes": notes
                }

                logger.debug(f"Search result: {result}")

                return result

            else:
                logger.warning("No matching contacts found.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No matching contact found"
                )

    except sqlite3.Error as e:
        logger.error(f"Error searching contacts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search contacts due to a database error: {e}"
        )