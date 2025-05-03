"""
This module provides FastAPI endpoints and utility functions for managing the operational mode of the application
using a SQLite-backed status database.

Key Features:
- Ensures the existence of a status database and initializes it if missing.
- Provides endpoints to set and retrieve the current mode.
- Handles database creation, error logging, and HTTP error responses.

Endpoints:
- POST /mode/{mode}: Sets the current mode in the status database.
- GET /mode: Retrieves the current mode from the status database.

Functions:
- verify_database(): Ensures the status database and required table exist, initializing with a default mode if necessary.
- mode_set(mode: str): FastAPI endpoint to set the mode.
- mode_get(): FastAPI endpoint to get the current mode.

Dependencies:
- FastAPI for API routing and responses.
- SQLite3 for lightweight database storage.
- Logging for error and event reporting.
- app.config for configuration, specifically the STATUS_DB path.

"""
import app.config

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
router = APIRouter()


def verify_database():
    """
    Verify the existence of the status database. If it doesn't exist, create it along with its parent directory.

    This function checks if the SQLite database specified by `app.config.STATUS_DB` exists.
    If it does not exist, it creates the necessary parent directories and establishes a new connection to the SQLite
    database. It then creates a table named 'status' with columns for 'key' and 'value', and inserts an initial record
    with the key 'mode' and value 'default'.

    The function returns immediately if the database already exists.

    Returns:
        None

    Raises:
        None
    """
    # Check the database path, return if it exists
    db_path = Path(app.config.STATUS_DB)

    if db_path.exists():
        return

    # Create the directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to (or create) the SQLite database
    with sqlite3.connect(app.config.STATUS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("CREATE TABLE IF NOT EXISTS status (key, value)")
        cursor.execute("INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",("mode", "default"))

        # Commit and close
        conn.commit()


@router.post("/mode/{mode}", response_model=dict)
def mode_set(mode: str) -> JSONResponse:
    """
    Set the current mode in the status database.

    Args:
        mode (str): The mode to set in the database.

    Returns:
        JSONResponse: A response indicating successful mode change.

    Raises:
        HTTPException: If a database error or unexpected error occurs during mode setting.
    """

    mode = mode.lower()

    try:
        verify_database()
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",
                ('mode', mode)
            )
            conn.commit()

        logger.info(f"✅ Mode successfully set to {mode}")
        return JSONResponse(
            content={"message": "Mode changed successfully"},
            status_code=status.HTTP_200_OK
        )

    except Exception as err:
        # Log any unexpected error.
        logger.exception(f"Unexpected error while setting mode: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while setting mode: {err}"
        )


@router.get("/mode", response_model=dict)
def mode_get() -> JSONResponse:
    """
    Retrieve the current mode from the status database.

    Returns:
        JSONResponse: A response containing the current mode or a 404 status if no mode is set.
        Returns HTTP 500 if a database or unexpected error occurs.

    Raises:
        HTTPException: If a database error or unexpected error prevents mode retrieval.
    """
    logger.debug("🤖 Attempting to retrieve the current mode.")

    try:
        verify_database()
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("SELECT value FROM status WHERE key='mode'")
            row = cursor.fetchone()

        if row is not None:
            mode_value = row[0]

            return JSONResponse(
                content={"message": mode_value},
                status_code=status.HTTP_200_OK
            )
        else:
            logger.warning("⚠️ Mode not set in the database.")
            return JSONResponse(
                content={"message": "Mode not set."},
                status_code=status.HTTP_404_NOT_FOUND
            )

    except Exception as err:
        logger.exception(f"Unexpected error while retrieving mode: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving mode: {err}"
        )