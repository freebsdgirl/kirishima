"""
FastAPI router for managing system mode status via SQLite database.

This module provides two API endpoints:
- POST /status/mode: Set the current system mode
- GET /status/mode: Retrieve the current system mode

The mode is stored and retrieved from a SQLite database configured in the application's config.
"""
import app.config

import sqlite3

from shared.log_config import get_logger
logger = get_logger(__name__)

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
router = APIRouter()


@router.post("/status/mode/{mode}", response_model=dict)
def mode_set(mode: str) -> JSONResponse:
    """
    Set the current mode in the status database.

    Args:
        mode (str): The mode to set in the status database.

    Returns:
        JSONResponse: A response indicating successful mode change with a 200 OK status,
        or an HTTPException if an error occurs during mode setting.

    Raises:
        HTTPException: If an internal server error occurs during mode setting.
    """
    logger.debug(f"🔄 Setting mode to {mode}.")
    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO status (key, value)
                VALUES (?, ?)
            """, ('mode', mode))
            conn.commit()

        return JSONResponse(
            content={"message": "Mode changed successfully"},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/status/mode")
def mode_get():
    """
    Retrieve the current mode from the status database.

    Returns:
        JSONResponse: A response containing the current mode if set,
        or a 404 status if no mode is configured.

    Raises:
        HTTPException: If an internal server error occurs during mode retrieval.
    """
    logger.debug("🤖 Getting mode.")

    try:
        with sqlite3.connect(app.config.STATUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM status WHERE key='mode'")
            row = cursor.fetchone()

        if row:
            return JSONResponse(
                content={"message": row[0]},
                status_code=status.HTTP_200_OK
            )

        else:
            return JSONResponse(
                content={"message": "Mode not set."},
                status_code=status.HTTP_404_NOT_FOUND
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
