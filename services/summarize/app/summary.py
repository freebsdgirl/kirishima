"""
This module provides FastAPI routes for managing summaries in a storage system. It includes
functionality for adding, retrieving, deleting, and searching summaries, as well as handling
summaries associated with specific users.
Routes:
    - POST /summary: Add a new summary.
    - GET /summary/{id}: Retrieve a specific summary by its unique identifier.
    - DELETE /summary/{id}: Delete a specific summary by its unique identifier.
    - GET /summary/user/{user_id}: Retrieve all summaries associated with a specific user.
    - DELETE /summary/user/{user_id}: Delete all summaries associated with a specific user.
    - GET /summary/search: Search summaries using a query string.
Models:
    - SummaryMetadata: Represents metadata associated with a summary entry.
    - SummaryEntry: Represents a complete summary entry with its unique identifier, text content, and associated metadata.
    - AddSummaryResponse: Represents the response returned after successfully adding a summary.
    - DeleteResponse: Represents the response returned after a delete operation.
Dependencies:
    - FastAPI: For creating API routes and handling HTTP requests.
    - Pydantic: For data validation and serialization.
    - Requests: For making HTTP requests to the ChromaDB service.
    - Shared modules: For logging and shared models.
Environment Variables:
    - CHROMADB_HOST: Hostname for the ChromaDB service (default: "localhost").
    - CHROMADB_PORT: Port for the ChromaDB service (default: "4206").
    - HTTPException: Raised when an operation fails, with appropriate status codes and error details.
"""
from shared.models.summarize import SummarizeRequest

from shared.log_config import get_logger
logger = get_logger(__name__)

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import requests


import os
chromadb_host = os.getenv("CHROMADB_HOST", "localhost")
chromadb_port = os.getenv("CHROMADB_PORT", "4206")
chromadb_url = f"http://{chromadb_host}:{chromadb_port}"


from fastapi import FastAPI, HTTPException, status, APIRouter
router = APIRouter()


class SummaryMetadata(BaseModel):
    """
    Represents metadata associated with a summary entry.
    
    Attributes:
        user_id (str): Unique identifier of the user who created the summary.
        platform (str): Platform from which the summary was generated.
        timestamp (str): Timestamp indicating when the summary was created.
    """
    user_id: str
    platform: str
    timestamp: str


class SummaryEntry(BaseModel):
    """
    Represents a complete summary entry with its unique identifier, text content, and associated metadata.
    
    Attributes:
        id (str): Unique identifier for the summary entry.
        text (str): The full text of the summary.
        metadata (SummaryMetadata): Metadata associated with the summary, including user, platform, and timestamp information.
    """
    id: str
    text: str
    metadata: SummaryMetadata


class AddSummaryResponse(BaseModel):
    """
    Represents the response returned after successfully adding a summary.
    
    Attributes:
        status (str): Indicates the result of the summary addition operation.
        id (str): The unique identifier assigned to the newly added summary.
    """
    status: str
    id: str


class DeleteResponse(BaseModel):
    """
    Represents the response returned after a delete operation.
    
    Attributes:
        status (str): Indicates the result of the delete operation.
        message (Optional[str], optional): Additional information or error details about the delete operation. Defaults to None.
    """
    status: str
    message: Optional[str] = None


@router.post("", response_model=AddSummaryResponse)
def add_summary(summarize_request: SummarizeRequest) -> AddSummaryResponse:
    """
    Add a new summary to the storage system.

    Sends a summary request to ChromaDB and returns the stored summary's metadata.
    Raises an HTTPException if the summary storage fails.

    Args:
        summarize_request (SummarizeRequest): The summary request containing text, user ID, platform, and save preferences.

    Returns:
        AddSummaryResponse: Metadata of the stored summary, including its unique ID.
    """
    logger.debug(f"POST /summary → {chromadb_url}/summary | user_id={summarize_request.user_id}")

    try:
        response = requests.post(
            f"{chromadb_url}/summary",
            json=summarize_request.model_dump()
        )

        response.raise_for_status()
        data = AddSummaryResponse.model_validate(response.json())
        logger.info(f"✅ Stored summary {data.id} for user {summarize_request.user_id}")
        return data

    except Exception as e:
        logger.error(f"❌ Error storing summary: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store summary"
        )


@router.get("/{id}", response_model=SummaryEntry)
def get_summary(id: str) -> SummaryEntry:
    """
    Retrieve a specific summary by its unique identifier.

    Fetches a summary from ChromaDB using the provided ID and returns the summary entry.
    Raises an HTTPException if the summary retrieval fails.

    Args:
        id (str): The unique identifier of the summary to retrieve.

    Returns:
        SummaryEntry: The retrieved summary entry.

    Raises:
        HTTPException: If there is an error retrieving the summary from the database.
    """
    logger.debug(f"GET /summary/{id} → {chromadb_url}/summary/{id}")

    try:
        response = requests.get(f"{chromadb_url}/summary/{id}")
        response.raise_for_status()
        data = SummaryEntry.model_validate(response.json())
        return data

    except Exception as e:
        logger.error(f"❌ Error fetching summary {id}: {e}")
    
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summary"
        )


@router.delete("/{id}", response_model=DeleteResponse)
def delete_summary(id: str) -> DeleteResponse:
    """
    Delete a specific summary by its unique identifier.

    Sends a delete request to ChromaDB to remove a summary with the given ID.
    Raises an HTTPException if the summary deletion fails.

    Args:
        id (str): The unique identifier of the summary to delete.

    Returns:
        DeleteResponse: The response from the deletion operation.

    Raises:
        HTTPException: If there is an error deleting the summary from the database.
    """
    logger.debug(f"DELETE /summary/{id} → {chromadb_url}/summary/{id}")

    try:
        response = requests.delete(f"{chromadb_url}/summary/{id}")
        response.raise_for_status()
        return DeleteResponse.model_validate(response.json())

    except Exception as e:
        logger.error(f"❌ Error deleting summary {id}: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete summary"
        )


@router.get("/user/{user_id}", response_model=List[SummaryEntry])
def get_user_summary(user_id: str) -> List[SummaryEntry]:
    """
    Retrieve all summaries associated with a specific user.

    Sends a GET request to ChromaDB to fetch summaries for the given user ID.
    Returns a list of SummaryEntry objects or raises an HTTPException if retrieval fails.

    Args:
        user_id (str): The unique identifier of the user whose summaries are to be retrieved.

    Returns:
        List[SummaryEntry]: A list of summary entries for the specified user.

    Raises:
        HTTPException: If there is an error retrieving the user's summaries from the database.
    """
    logger.debug(f"GET /summary/user/{user_id} → {chromadb_url}/summary/user/{user_id}")

    try:
        response = requests.get(f"{chromadb_url}/summary/user/{user_id}")
        response.raise_for_status()
        parsed = [SummaryEntry.model_validate(obj) for obj in response.json()]
        logger.debug(f"📦 Retrieved {len(parsed)} summaries for user {user_id}")
        return parsed

    except Exception as e:
        logger.error(f"❌ Error retrieving summaries for user {user_id}: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user summaries"
        )


@router.delete("/user/{user_id}", response_model=DeleteResponse)
def delete_user_summaries(user_id: str):
    """
    Delete all summaries associated with a specific user.

    Sends a DELETE request to ChromaDB to remove all summaries for the given user ID.
    Returns a DeleteResponse or raises an HTTPException if deletion fails.

    Args:
        user_id (str): The unique identifier of the user whose summaries are to be deleted.

    Returns:
        DeleteResponse: Confirmation of successful summary deletion.

    Raises:
        HTTPException: If there is an error deleting the user's summaries from the database.
    """
    logger.debug(f"DELETE /summary/user/{user_id} → {chromadb_url}/summary/user/{user_id}")

    try:
        response = requests.delete(f"{chromadb_url}/summary/user/{user_id}")
        response.raise_for_status()
        return DeleteResponse.model_validate(response.json())

    except Exception as e:
        logger.error(f"❌ Error deleting summaries for user {user_id}: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user summaries"
        )


@router.get("/search", response_model=List[SummaryEntry])
def search_summary(q: str) -> List[SummaryEntry]:
    """
    Search summaries using a query string.

    Sends a GET request to ChromaDB to perform a search across summaries.
    Returns a list of matching SummaryEntry objects or raises an HTTPException if the search fails.

    Args:
        q (str): The search query string.

    Returns:
        List[SummaryEntry]: A list of summary entries matching the search query.

    Raises:
        HTTPException: If there is an error performing the summary search.
    """
    logger.debug(f"GET /summary/search?q={q} → {chromadb_url}/summary/search")

    try:
        response = requests.get(f"{chromadb_url}/summary/search", params={"q": q})
        response.raise_for_status()
        parsed = [SummaryEntry.model_validate(obj) for obj in response.json()]
        logger.debug(f"🔎 Search matched {len(parsed)} entries")
        return parsed

    except Exception as e:
        logger.error(f"❌ Error performing summary search: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search summaries"
        )
