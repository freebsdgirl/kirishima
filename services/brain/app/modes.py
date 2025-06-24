"""
This module provides API endpoints and utility functions for managing the operational mode of the application.
Features:
- Loads and saves the current mode to a SQLite status database.
- Exposes FastAPI endpoints to get and set the current mode.
- Caches the current mode in a global variable for efficient access.
- Initializes the mode from the database during application startup using FastAPI's lifespan context.
Endpoints:
- POST /mode/{mode}: Set the current mode.
- GET /mode: Retrieve the current mode.
- HTTPException: For API errors.
- sqlite3.Error: For database access errors.
"""
import app.config

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
import json

from fastapi import APIRouter, HTTPException, status, FastAPI
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager


router = APIRouter()
current_mode = None  # Global variable to cache the mode


def load_mode_from_db():
    """
    Loads the current mode from the status database.
    
    Retrieves the mode value from the 'status' table using the 'mode' key. 
    If no mode is found, sets the current mode to 'default'.
    
    Updates the global `current_mode` variable with the retrieved or default mode.
    
    Raises:
        sqlite3.Error: If there's an issue connecting to or querying the database.
    """
    global current_mode


    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["status"]
    if not db:
        logger.error("Database path is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database path is not configured."
        )

    with sqlite3.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM status WHERE key='mode'")
        row = cursor.fetchone()
        current_mode = row[0] if row else 'default'


def save_mode_to_db(mode: str):
    """
    Saves the current mode to the status database.
    
    Connects to the SQLite database and inserts or replaces the 'mode' key 
    with the provided mode value. Uses Write-Ahead Logging (WAL) for improved 
    concurrency and performance. Commits the transaction after insertion.
    
    Args:
        mode (str): The mode to be saved in the database.
    """

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["status"]
    if not db:
        logger.error("Database path is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database path is not configured."
        )

    with sqlite3.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute(
            "INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",
            ('mode', mode)
        )
        conn.commit()


@router.post("/mode/{mode}", response_model=dict)
def mode_set(mode: str) -> JSONResponse:
    """
    Set the current mode via API endpoint.

    Accepts a mode as a path parameter, converts it to lowercase, and saves it to the database.
    Updates the global current_mode variable and logs the successful mode change.

    Args:
        mode (str): The mode to set, which will be converted to lowercase.

    Returns:
        JSONResponse: A 200 OK response with a success message if mode is set successfully.

    Raises:
        HTTPException: A 500 Internal Server Error if an unexpected error occurs during mode setting.
    """
    global current_mode
    mode = mode.lower()

    try:
        save_mode_to_db(mode)
        current_mode = mode
        logger.info(f"✅ Mode successfully set to {mode}")

        return JSONResponse(
            content={"message": "Mode changed successfully"},
            status_code=status.HTTP_200_OK
        )

    except Exception as err:
        logger.exception(f"Unexpected error while setting mode: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while setting mode: {err}"
        )


@router.get("/mode", response_model=dict)
def mode_get() -> JSONResponse:
    """
    Retrieve the current mode via API endpoint.

    Returns the current mode if set, otherwise returns a 404 Not Found response.
    Logs a warning if no mode is currently set.

    Returns:
        JSONResponse: A 200 OK response with the current mode, or a 404 Not Found response
        if no mode is set.
    """
    if current_mode is not None:
        return JSONResponse(
            content={"message": current_mode},
            status_code=status.HTTP_200_OK
        )
    else:
        logger.warning("⚠️ Mode not set in the database.")
        return JSONResponse(
            content={"message": "Mode not set."},
            status_code=status.HTTP_404_NOT_FOUND
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async context manager for initializing the application mode.

    Loads the mode from the database during application startup.
    Yields control back to the application after initialization.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Provides a context for application lifespan management.
    """
    load_mode_from_db()
    yield
