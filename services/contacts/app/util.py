

import app.config as config

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

import sqlite3
from fastapi import HTTPException, status

def get_db_connection():
    """
    Establish a connection to the SQLite database.
    Enables foreign key constraints for referential integrity.
    
    Returns:
        sqlite3.Connection: An active database connection using the configured database path.
    """
    conn = sqlite3.connect(config.CONTACTS_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def check_admin_alias_uniqueness(conn, contact_id, aliases):
    """
    Checks if the '@ADMIN' alias is unique across contacts.
    
    Verifies that the '@ADMIN' alias is not already assigned to another contact.
    Raises an HTTPException if the alias is already in use by a different contact.
    
    Args:
        conn (sqlite3.Connection): Database connection.
        contact_id (str, optional): ID of the current contact to exclude from the uniqueness check.
        aliases (list, optional): List of aliases to check.
    
    Raises:
        HTTPException: If '@ADMIN' alias is already assigned to another user.
    """
    if aliases is None:
        return
    if "@ADMIN" in aliases:
        cursor = conn.cursor()
        cursor.execute("SELECT contact_id FROM aliases WHERE alias = ? AND contact_id != ?", ("@ADMIN", contact_id or ""))
        row = cursor.fetchone()
        if row:
            logger.error(f"Permission denied: '@ADMIN' alias is already assigned to another user.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Permission denied: '@ADMIN' alias is already assigned to another user."
            )