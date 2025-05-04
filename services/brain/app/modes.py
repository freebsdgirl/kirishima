"""
This module provides FastAPI endpoints for setting and retrieving the current mode
in the application's status database.

Endpoints:
    - POST /mode/{mode}: Sets the current mode in the status database.
    - GET /mode: Retrieves the current mode from the status database.

The endpoints interact with a SQLite database defined by `app.config.STATUS_DB`.
Logging is performed for key actions and error handling is implemented to return
appropriate HTTP responses in case of database or unexpected errors.
"""
import app.config

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
router = APIRouter()


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