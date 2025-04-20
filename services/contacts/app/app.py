"""
This module provides a FastAPI application for managing contacts. It includes endpoints for creating, 
retrieving, updating, deleting, and searching contacts. The application interacts with an SQLite database 
to store contact information, including notes, aliases, and additional fields.
The following endpoints are available:
- POST /contact: Create a new contact.
- GET /contacts: Retrieve a list of all contacts.
- PUT /contact/{contact_id}: Replace an existing contact with new information.
- PATCH /contact/{contact_id}: Partially update an existing contact.
- DELETE /contact/{contact_id}: Delete a contact by ID.
- GET /search: Search for contacts by alias, field key, or field value.
The application uses a modular structure, with shared components for logging, configuration, and tracing. 
Database operations are performed using SQLite, and the application ensures proper error handling for 
database-related issues.
Dependencies:
- FastAPI: For building the web application.
- SQLite3: For database operations.
- Shared modules: For logging, configuration, and tracing.
Key Features:
- UUID-based unique identifiers for contacts.
- Support for aliases and custom fields.
- Comprehensive error handling with HTTP exceptions.
- Modular and extensible design for shared functionality.
"""

import app.config as config

from app.docs import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

from shared.models.contacts import ContactCreate, Contact

import sqlite3
import uuid
from typing import Optional


from fastapi import FastAPI, HTTPException, Query, status
app = FastAPI()
app.include_router(routes_router, tags=["system"])
register_list_routes(app)
app.include_router(docs_router, tags=["docs"])


import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="contacts")


def get_db_connection():
    """
    Establish a connection to the SQLite database.
    
    Returns:
        sqlite3.Connection: An active database connection using the configured database path.
    """
    return sqlite3.connect(config.CONTACTS_DB)


@app.post("/contact", response_model=Contact)
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


@app.get("/contacts", response_model=list[Contact])
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


@app.put("/contact/{contact_id}", response_model=Contact)
def replace_contact(contact_id: str, contact: ContactCreate) -> dict:
    """
    Replace an existing contact with new information.

    Completely replaces the contact's notes, aliases, and fields with the provided data.
    Verifies the contact exists before performing the replacement. Raises an HTTP 404 error
    if the contact is not found, or an HTTP 500 error if a database error occurs.

    Args:
        contact_id (str): The unique identifier of the contact to replace.
        contact (ContactCreate): The new contact information to replace the existing contact.

    Returns:
        dict: A dictionary containing the contact ID and a status of "replaced".

    Raises:
        HTTPException: 404 if the contact is not found, 500 if a database error occurs.
    """

    logger.debug(f"/contact/{contact_id} Request:\n{contact.model_dump_json(indent=4)}")

    try:
        with get_db_connection() as conn:
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

            for field in contact.fields:
                cursor.execute(
                    "INSERT INTO fields (contact_id, key, value) VALUES (?, ?, ?)",
                    (contact_id, field.get("key"), field.get("value"))
                )

            conn.commit()

    except sqlite3.Error as e:
        logger.error(f"Error replacing contact {contact_id}: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to replace contact due to a database error"
        )

    logger.debug(f"Contact {contact_id} replaced successfully.")

    return {
        "id": contact_id,
        "status": "replaced"
    }


@app.patch("/contact/{contact_id}", response_model=Contact)
def patch_contact(contact_id: str, contact: ContactCreate) -> dict:
    """
    Partially update an existing contact by ID.

    Allows updating notes, adding aliases, and adding fields for a specific contact.
    Raises an error if the contact does not exist.

    Args:
        contact_id (str): The unique identifier of the contact to update.
        contact (ContactCreate): The partial contact information to update.

    Returns:
        dict: A dictionary containing the contact ID and a status of "patched".

    Raises:
        HTTPException: 404 if the contact is not found, 500 if a database error occurs.
    """
    logger.debug(f"/contact/{contact_id} Request:\n{contact.model_dump_json(indent=4)}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT notes FROM contacts WHERE id = ?", (contact_id,))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contact not found"
                )

            # Update notes if provided
            if contact.notes is not None:
                cursor.execute("UPDATE contacts SET notes = ? WHERE id = ?", (contact.notes, contact_id))

            for alias in contact.aliases:
                cursor.execute("INSERT INTO aliases (contact_id, alias) VALUES (?, ?)", (contact_id, alias))

            for field in contact.fields:
                cursor.execute(
                    "INSERT INTO fields (contact_id, key, value) VALUES (?, ?, ?)",
                    (contact_id, field.get("key"), field.get("value"))
                )

            conn.commit()

    except sqlite3.Error as e:
        logger.error(f"Error patching contact {contact_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to patch contact due to a database error"
        )

    logger.debug(f"Contact {contact_id} patched successfully.")

    return {
        "id": contact_id,
        "status": "patched"
    }


@app.delete("/contact/{contact_id}", response_model=dict)
def delete_contact(contact_id: str) -> dict:
    """
    Deletes a contact and its associated data from the database.

    Args:
        contact_id (str): The unique identifier of the contact to delete.

    Returns:
        dict: A dictionary containing the contact ID and a status of "deleted".

    Raises:
        HTTPException: 404 if the contact is not found, 500 if a database error occurs.
    """
    logger.debug(f"/contact/{contact_id} Request: delete contact")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM contacts WHERE id = ?", (contact_id,))

            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contact not found"
                )

            cursor.execute("DELETE FROM aliases WHERE contact_id = ?", (contact_id,))
            cursor.execute("DELETE FROM fields WHERE contact_id = ?", (contact_id,))
            cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))

            conn.commit()

    except sqlite3.Error as e:
        logger.error(f"Error deleting contact {contact_id}: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete contact due to a database error"
        )

    logger.debug(f"Contact {contact_id} deleted successfully.")

    return {
        "id": contact_id,
        "status": "deleted"
    }


@app.get("/search", response_model=Contact)
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
