"""
This module provides an API endpoint for deleting a contact and its associated data 
from the database. It defines a FastAPI router with a single DELETE operation.

Functions:
    delete_contact(contact_id: str) -> dict:
"""

from app.util import get_db_connection

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

import sqlite3

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.delete("/contact/{contact_id}", response_model=dict)
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