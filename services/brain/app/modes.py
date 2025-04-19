"""
This module provides FastAPI endpoints for setting and retrieving the current mode
stored in a SQLite database. It includes two endpoints:
1. `POST /mode/{mode}`: Sets the current mode in the database.
2. `GET /mode`: Retrieves the current mode from the database.
The module uses the following components:
- `sqlite3` for database operations.
- `FastAPI` for defining API routes and handling HTTP requests.
- `shared.log_config.get_logger` for logging.
Functions:
- `mode_set(mode: str) -> JSONResponse`: Sets the mode in the database and returns a success message.
- `mode_get() -> JSONResponse`: Retrieves the current mode from the database and returns it.
Error Handling:
- Handles SQLite-specific errors and logs them with full stack traces.
- Handles unexpected errors and logs them appropriately.
- Raises `HTTPException` with appropriate status codes for client and server errors.
Logging:
- Logs debug, info, warning, and exception messages for better traceability.
"""

import app.config
import sqlite3
from pathlib import Path

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

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

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to (or create) the SQLite database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create table
    cursor.execute("CREATE TABLE IF NOT EXISTS status (key, value)")
    cursor.execute("INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",("mode", "default"))

    # Commit and close
    conn.commit()
    conn.close()


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
    logger.debug("🔄 Attempting to set mode to '%s'", mode)

    try:
        verify_database()
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",
                ('mode', mode)
            )
            conn.commit()

        logger.info("✅ Mode successfully set to '%s'.", mode)
        return JSONResponse(
            content={"message": "Mode changed successfully"},
            status_code=status.HTTP_200_OK
        )

    except sqlite3.Error as db_err:
        # Log database-specific errors with the full stack trace.
        logger.exception("SQLite error occurred while setting mode: %s", db_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while setting mode."
        )

    except Exception as err:
        # Log any unexpected error.
        logger.exception("Unexpected error while setting mode: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while setting mode."
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
            cursor.execute("SELECT value FROM status WHERE key='mode'")
            row = cursor.fetchone()

        if row is not None:
            mode_value = row[0]
            logger.info("✅ Mode retrieved successfully: %s", mode_value)
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

    except sqlite3.Error as db_err:
        logger.exception("SQLite error occurred while retrieving mode: %s", db_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving mode."
        )

    except Exception as err:
        logger.exception("Unexpected error while retrieving mode: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving mode."
        )