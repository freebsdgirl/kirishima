"""
This module provides FastAPI endpoints for managing and retrieving contact information.
Endpoints:
    - GET /contacts: Retrieve a list of all contacts with their details.
    - GET /search: Search for a specific contact based on query parameters.
Functions:
    - list_contacts: Fetches all contacts from the database, including their unique identifiers,
      notes, aliases, and additional fields. Returns a comprehensive list of contact information
      or raises an HTTP 500 error if a database error occurs.
    - search_contacts: Searches for a specific contact using exact, case-insensitive matches
      based on query parameters. Supports targeted searches by field key and value or a generic
      search by alias or field value. Returns the first matching contact or raises appropriate
      HTTP exceptions for errors or missing parameters.
Dependencies:
    - FastAPI for API routing and HTTP exception handling.
    - SQLite for database operations.
    - Shared utilities for logging and database connection management.
    - Pydantic models for response validation.
    - HTTPException: For various error scenarios, including database errors, missing parameters,
      or no matching contacts found.
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

                cursor.execute("SELECT key, value FROM fields WHERE contact_id = ?", (contact_id,))
                fields = [{"key": row[0], "value": row[1]} for row in cursor.fetchall()]

                result.append({
                    "id": contact_id,
                    "aliases": aliases,
                    "fields": fields,
                    "notes": notes
                })

    except sqlite3.Error as e:
        logger.error(f"Error listing contacts: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list contacts due to a database error: {e}"
        )

    return result


@router.get("/search", response_model=Contact)
def search_contacts(
    q: Optional[str] = Query(None, description="General search by alias or field value (exact match, case-insensitive)"),
    key: Optional[str] = Query(None, description="Field key to search on (e.g., platform)"),
    value: Optional[str] = Query(None, description="Field value to search for (e.g., sender_id)")
) -> dict:
    """
    Search contacts with an exact, case-insensitive match.
    
    If both 'key' and 'value' are provided, it searches the fields table for a record
    where the key matches 'key' and the value matches 'value'. Otherwise, if 'q' is provided,
    it falls back to a generic search in aliases and field values.
    
    Returns:
        dict: The first matching contact.
    
    Raises:
        HTTPException: 404 if no matching contact is found, 400 if missing parameters, 500 on database errors.
    """
    logger.debug(f"/search Request: q={q}, key={key}, value={value}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            contact_ids = set()

            if key is not None and value is not None:
                # Perform targeted search in fields table
                cursor.execute(
                    "SELECT contact_id FROM fields WHERE key = ? COLLATE NOCASE AND value = ? COLLATE NOCASE",
                    (key, value)
                )

                contact_ids.update(row[0] for row in cursor.fetchall())

            elif q is not None:
                # Fallback generic search on aliases and fields values
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
                fields = [{"key": row[0], "value": row[1]} for row in cursor.fetchall()]

                result = {
                    "id": contact_id,
                    "aliases": aliases,
                    "fields": fields,
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