"""
This module provides FastAPI routes and Pydantic models for managing a rolling buffer database.
The rolling buffer database is used to store and retrieve conversation messages and summaries. 
It includes functionality to insert new conversation entries and fetch summaries in a structured format.
Modules:
    - app.config: Contains application configuration, including database paths.
    - shared.log_config: Provides logging configuration and utilities.
    - pydantic: Used for data validation and serialization.
    - sqlite3: Used for interacting with the SQLite database.
    - fastapi: Provides the web framework for defining API routes.
Classes:
    - BufferMessage: A Pydantic model representing a message entry for the rolling buffer database.
Routes:
    - POST /buffer/conversation: Inserts a conversation entry into the rolling buffer database.
    - GET /buffer/conversation: Retrieves all conversation summaries from the rolling buffer database.
Exceptions:
    - HTTPException: Raised with a 500 Internal Server Error status code if database operations fail.
"""

import app.config

from shared.log_config import get_logger
logger = get_logger(__name__)

from pydantic import BaseModel
import sqlite3

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


class BufferMessage(BaseModel):
    """
    Represents a message entry for the rolling buffer database.
    
    Attributes:
        sender (str): The sender of the message.
        content (str): The content of the message.
        timestamp (str): The timestamp of when the message was sent.
        platform (str): The platform from which the message originated.
        mode (str): The mode or context of the message.
    """
    sender: str
    content: str
    timestamp: str
    platform: str
    mode: str


@router.post("/buffer/conversation", response_model=dict)
def insert_conversation(entry: BufferMessage) -> dict:
    """
    Insert a conversation entry into the rolling buffer database.

    Args:
        entry (BufferMessage): The conversation message to be stored, containing sender, 
        content, timestamp, platform, and mode information.

    Returns:
        dict: A success status message indicating the buffer entry was stored.

    Raises:
        HTTPException: If there is an error during database insertion, with a 500 Internal Server Error.
    """
    logger.debug("Adding message.")

    try:
        conn = sqlite3.connect(app.config.ROLLING_BUFFER_DB)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO rolling_buffer (sender, content, timestamp, platform, mode)
            VALUES (?, ?, ?, ?, ?)
        """, (entry.sender, entry.content, entry.timestamp, entry.platform, entry.mode))

        conn.commit()
        conn.close()

        return {
            "status": "success", 
            "message": "Buffer entry stored."
        }

    except Exception as e:
        logger.error(f"Error adding buffery entry: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding buffery entry: {e}"
        )


@router.get("/buffer/conversation", response_model=list)
def create_buffer_prompt() -> list:
    """
    Retrieve all conversation summaries from the rolling buffer database.

    Fetches summaries from the database, ordered by timestamp in ascending order.

    Returns:
        list: A list of summary dictionaries, each containing 'summary' and 'timestamp' keys.

    Raises:
        HTTPException: If there is an error retrieving summaries from the database, with a 500 status code.
    """
    try:
        conn = sqlite3.connect(app.config.ROLLING_BUFFER_DB)
        cursor = conn.cursor()

        cursor.execute("SELECT summary, timestamp FROM summaries ORDER BY timestamp ASC")

        rows = cursor.fetchall()
        summaries = [{"summary": row[0], "timestamp": row[1]} for row in rows]

        conn.close()

        return summaries
    
    except Exception as e:
        logger.error(f"Error retrieving summaries: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving summaries: {e}"
        )
