"""
This module defines a FastAPI router for managing buffer-related API endpoints in the ChromaDB memory management system.
The buffer is used to store and retrieve text entries associated with specific users and platforms. The module provides
endpoints for adding, retrieving, and deleting buffer entries, as well as retrieving all entries or entries specific to
a user.
Classes:
    BufferEntry (BaseModel): Represents a buffer entry containing text, user ID, platform, and timestamp.
Routes:
    - POST "": Add a new buffer entry to the collection.
    - GET "": Retrieve all buffer entries from the collection.
    - GET "/{user_id}": Retrieve buffer entries for a specific user.
    - DELETE "/{user_id}": Delete all buffer entries for a specific user.
Dependencies:
    - app.config: Configuration module for accessing ChromaDB client and collection settings.
    - app.embedding: Module for generating embeddings for text entries.
    - shared.log_config: Module for logging configuration.
    - fastapi: Framework for building API endpoints.
    - pydantic: Library for data validation and settings management.
    - datetime: Standard library module for handling date and time.
    - uuid: Standard library module for generating unique identifiers.
Error Handling:
    All endpoints raise HTTPException with a 500 Internal Server Error status code in case of failures.
"""

import app.config

from app.embedding import get_embedding, EmbeddingRequest

from shared.log_config import get_logger
logger = get_logger(__name__)

from fastapi import HTTPException, status, APIRouter
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


"""
FastAPI router for handling memory-related API endpoints.

This router is used to define and organize routes related to memory search and retrieval
in the ChromaDB memory management system.
"""
router = APIRouter()


class BufferEntry(BaseModel):
    """
    Represents an entry in the user's buffer for storing text from a specific platform.
    
    Attributes:
        text (str): The text content of the buffer entry.
        user_id (str): The unique identifier of the user associated with the buffer entry.
        platform (str): The platform from which the text was sourced.
        timestamp (datetime): The timestamp of when the buffer entry was created, defaulting to the current UTC time.
    """
    text: str
    user_id: str
    platform: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now().isoformat())


@router.post("", response_model=dict)
def add_to_buffer(buffer_entry: BufferEntry) -> dict:
    """
    Add a new entry to the user's buffer collection.

    This endpoint creates a new buffer entry by generating an embedding for the text,
    storing the entry in ChromaDB with associated metadata, and returning a unique document ID.

    Args:
        buffer_entry (BufferEntry): The buffer entry containing text, user ID, platform, and timestamp.

    Returns:
        dict: A dictionary with a success status and the generated document ID.

    Raises:
        HTTPException: If there is an error adding the buffer entry, with a 500 Internal Server Error.
    """
    try:
        collection = app.config.client.get_or_create_collection(name=app.config.BUFFER_COLLECTION)

        logger.debug(f"📥 Embedding input text: {buffer_entry.text!r}")
        logger.debug(f"📥 Full buffer entry: {buffer_entry.dict()}")

        embedding = get_embedding(EmbeddingRequest(input=buffer_entry.text))
        doc_id = f"buffer-{uuid.uuid4()}"

        logger.debug(f"📥 Generated embedding: {embedding}")
        collection.add(
            documents=[buffer_entry.text],
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                "user_id": buffer_entry.user_id,
                "platform": buffer_entry.platform,
                "timestamp": buffer_entry.timestamp.isoformat()
            }]
        )

        logger.info(f"✅ Buffer entry stored: {doc_id}")
        return {
            "status": "success",
            "id": doc_id
        }

    except Exception as e:
        logger.error(f"Error adding to buffer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add to buffer: {e}"
        )


@router.get("", response_model=list)
def get_all_buffers() -> list:
    """
    Retrieve all buffer entries from the ChromaDB collection.

    This endpoint fetches all buffer entries, including their document IDs, text content,
    user information, platform, and timestamps.

    Returns:
        list: A list of dictionaries containing buffer entry details, with each entry
            including id, text, user_id, platform, and timestamp.

    Raises:
        HTTPException: If there is an error retrieving buffer contents, with a 500 Internal Server Error.
    """
    try:
        collection = app.config.client.get_or_create_collection(name=app.config.BUFFER_COLLECTION)
        results = collection.get(include=["documents", "metadatas"])

        response = []
        for doc_id, text, metadata in zip(results["ids"], results["documents"], results["metadatas"]):
            response.append({
                "id": doc_id,
                "text": text,
                "user_id": metadata.get("user_id"),
                "platform": metadata.get("platform"),
                "timestamp": metadata.get("timestamp")
            })

        return response

    except Exception as e:
        logger.error(f"Error retrieving buffer contents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve buffer contents"
        )


@router.get("/{user_id}", response_model=list)
def get_buffer(user_id: str) -> list:
    """
    Retrieve the buffer entries for a specific user.

    This endpoint fetches all buffer entries associated with a given user ID,
    including document IDs, text content, platform, and timestamps.

    Args:
        user_id (str): The unique identifier of the user whose buffer entries are to be retrieved.

    Returns:
        list: A list of dictionaries containing buffer entry details, with each entry
            including id, text, platform, and timestamp.

    Raises:
        HTTPException: If there is an error retrieving the user's buffer, with a 500 Internal Server Error.
    """
    try:
        collection = app.config.client.get_or_create_collection(name=app.config.BUFFER_COLLECTION)
        results = collection.get(
            where={"user_id": user_id},
            include=["documents", "metadatas"]
        )

        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        response = []
        for i in range(len(ids)):
            response.append({
                "id": ids[i],
                "text": documents[i],
                "platform": metadatas[i].get("platform"),
                "timestamp": metadatas[i].get("timestamp")
            })

        return response

    except Exception as e:
        logger.error(f"Error retrieving buffer for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user buffer"
        )


@router.delete("/{user_id}", response_model=dict)
def delete_buffer(user_id: str) -> dict:
    """
    Delete all buffer entries for a specific user.

    This endpoint removes all buffer entries associated with a given user ID
    from the buffer collection. If no entries exist, it returns a success
    response with zero deleted entries.

    Args:
        user_id (str): The unique identifier of the user whose buffer entries are to be deleted.

    Returns:
        dict: A dictionary containing the deletion status, number of deleted entries,
            and an optional message if no entries were found.

    Raises:
        HTTPException: If there is an error deleting the user's buffer, with a 500 Internal Server Error.
    """
    try:
        collection = app.config.client.get_or_create_collection(name=app.config.BUFFER_COLLECTION)
        results = collection.get(where={"user_id": user_id})

        if not results["ids"]:
            return {
                "status": "success", "deleted": 0,
                "message": "No buffer entries found for user."
            }

        collection.delete(ids=results["ids"])
        logger.info(f"🗑️ Deleted {len(results['ids'])} buffer entries for user {user_id}")

        return {
            "status": "success",
            "deleted": len(results["ids"])
        }

    except Exception as e:
        logger.error(f"Error deleting buffer for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete buffer entries"
        )