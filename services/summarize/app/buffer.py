"""
This module provides FastAPI routes for managing buffer entries in ChromaDB. 
It includes functionality to add, retrieve, and delete buffer entries, 
which are used for text summarization purposes.
Classes:
    BufferEntry: A Pydantic model representing an entry in the buffer for text summarization.
    BufferEntryResponse: A Pydantic model representing a response for a buffer entry.
    AddBufferResponse: A Pydantic model representing the response after adding a buffer entry.
    DeleteBufferResponse: A Pydantic model representing the response after deleting buffer entries.
Routes:
    POST /buffer:
        - Request Body: BufferEntry
        - Response: AddBufferResponse
        - Raises: HTTPException (500) if there is an error adding the buffer entry.
    GET /buffer:
        - Response: List[BufferEntryResponse]
        - Raises: HTTPException (500) if there is an error retrieving buffer entries.
    GET /buffer/{user_id}:
        - Path Parameter: user_id (str)
        - Response: List[BufferEntryResponse]
        - Raises: HTTPException (500) if there is an error retrieving the user's buffer entries.
    DELETE /buffer/{user_id}:
        - Path Parameter: user_id (str)
        - Response: DeleteBufferResponse
        - Raises: HTTPException (500) if there is an error deleting the user's buffer entries.
"""

from shared.models.summarize import MessageBufferEntry, AddMessageBufferResponse

from shared.log_config import get_logger
logger = get_logger(__name__)

from pydantic import BaseModel
import requests
from typing import List, Optional

import os
chromadb_host = os.getenv("CHROMADB_HOST", "localhost")
chromadb_port = os.getenv("CHROMADB_PORT", "4206")
chromadb_url = f"http://{chromadb_host}:{chromadb_port}"


from fastapi import APIRouter, HTTPException, status
router = APIRouter()


class BufferEntryResponse(BaseModel):
    """
    A Pydantic model representing a response for a buffer entry in text summarization.
    
    Attributes:
        id (str): Unique identifier for the buffer entry.
        text (str): The text content of the buffer entry.
        user_id (Optional[str]): Unique identifier for the user who created the buffer entry, if available.
        platform (Optional[str]): The platform or source of the text entry, if available.
        timestamp (Optional[str]): Timestamp of the entry in ISO 8601 format, if available.
    """
    id: str
    text: str
    user_id: Optional[str] = None
    platform: Optional[str] = None
    timestamp: Optional[str] = None


class DeleteBufferResponse(BaseModel):
    """
    A Pydantic model representing the response after deleting buffer entries.
    
    Attributes:
        status (str): The status of the buffer entry deletion operation.
        deleted (int): The number of buffer entries that were deleted.
        message (Optional[str], optional): An optional message providing additional details about the deletion. Defaults to None.
    """
    status: str
    deleted: int
    message: Optional[str] = None


@router.post("", response_model=AddMessageBufferResponse)
def add_to_buffer(entry: MessageBufferEntry) -> AddMessageBufferResponse:
    """
    Add a new entry to the buffer in ChromaDB.

    Args:
        entry (BufferEntry): The buffer entry to be added, which includes user details and text.

    Returns:
        AddBufferResponse: A response containing the status and ID of the added buffer entry.

    Raises:
        HTTPException: If there is an error adding the buffer entry, with a 500 Internal Server Error status.
    """
    logger.debug(f"POST /buffer: Adding entry for user_id={entry.user_id}")
    try:
        # Convert the entry to a dictionary
        entry_data = entry.model_dump()
        
        # Pop the 'source' value and prepend it to the text
        source = entry_data.pop("source", "User")
        entry_data["text"] = f"{source}: {entry_data['text']}"
        
        # Send the modified data to ChromaDB
        response = requests.post(f"{chromadb_url}/buffer", json=entry_data)
        response.raise_for_status()
        data = response.json()

        logger.debug(f"✅ ChromaDB responded with: {data}")
        return AddMessageBufferResponse(**data)

    except Exception as e:
        logger.error(f"❌ Error adding buffer entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add buffer entry"
        )


@router.get("", response_model=List[BufferEntryResponse])
def get_all_buffers() -> List[BufferEntryResponse]:
    """
    Retrieve all buffer entries from ChromaDB.

    Returns:
        List[BufferEntryResponse]: A list of all buffer entries.

    Raises:
        HTTPException: If there is an error retrieving buffer entries, with a 500 Internal Server Error status.
    """
    logger.debug("GET /buffer: Fetching all buffer entries")

    try:
        response = requests.get(f"{chromadb_url}/buffer")
        response.raise_for_status()
        data = response.json()

        logger.debug(f"✅ Received {len(data)} entries from ChromaDB")
        return [BufferEntryResponse(**entry) for entry in data]

    except Exception as e:
        logger.error(f"❌ Error retrieving all buffers: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve buffers"
        )


@router.get("/{user_id}", response_model=List[BufferEntryResponse])
def get_buffer(user_id: str) -> List[BufferEntryResponse]:
    """
    Retrieve buffer entries for a specific user from ChromaDB.

    Args:
        user_id (str): The unique identifier of the user whose buffer entries are to be retrieved.

    Returns:
        List[BufferEntryResponse]: A list of buffer entries for the specified user.

    Raises:
        HTTPException: If there is an error retrieving the user's buffer entries, with a 500 Internal Server Error status.
    """
    logger.debug(f"GET /buffer/{user_id}: Fetching buffer for user")

    try:
        response = requests.get(f"{chromadb_url}/buffer/{user_id}")

        response.raise_for_status()
        data = response.json()

        logger.debug(f"✅ Received {len(data)} entries for user {user_id}")
        return [BufferEntryResponse(**entry) for entry in data]

    except Exception as e:
        logger.error(f"❌ Error retrieving buffer for user {user_id}: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user buffer"
        )


@router.delete("/{user_id}", response_model=DeleteBufferResponse)
def delete_buffer(user_id: str) -> DeleteBufferResponse:
    """
    Delete buffer entries for a specific user from ChromaDB.

    Args:
        user_id (str): The unique identifier of the user whose buffer entries are to be deleted.

    Returns:
        DeleteBufferResponse: A response indicating the result of the buffer deletion operation.

    Raises:
        HTTPException: If there is an error deleting the user's buffer entries, with a 500 Internal Server Error status.
    """
    logger.debug(f"DELETE /buffer/{user_id}: Deleting buffer for user")

    try:
        response = requests.delete(f"{chromadb_url}/buffer/{user_id}")

        response.raise_for_status()
        data = response.json()

        logger.debug(f"✅ Deletion result for user {user_id}: {data}")
        return DeleteBufferResponse(**data)

    except Exception as e:
        logger.error(f"❌ Error deleting buffer for user {user_id}: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user buffer"
        )
