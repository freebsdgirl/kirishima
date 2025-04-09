"""
This module provides a FastAPI router for managing summarization-related API endpoints
in the ChromaDB memory management system. It includes functionality for adding, retrieving,
searching, and deleting summaries, as well as retrieving summaries for a specific user.

Classes:
    SummarizeRequest (BaseModel): Defines the request model for summarization jobs, including
        attributes such as text, platform, user ID, and timestamp.

Routes:
    @router.post(""):
        Add a new summary to the ChromaDB collection. Stores the summary text, its embedding,
        user metadata, and generates a unique document ID.

    @router.get("/{id}"):
        Retrieve a specific summary by its unique identifier. Returns the summary text and
        associated metadata.

    @router.get("/user/{user_id}"):

    @router.delete("/{id}"):

    @router.get("/search"):
        Search summaries with optional filtering by user, platform, and timestamp. Supports
        semantic search using embeddings.

Exceptions:
    HTTPException: Raised for various error scenarios, such as failure to add, retrieve,
        delete, or search summaries.

Dependencies:
    - chroma.config: Configuration for ChromaDB client and collections.
    - chroma.embedding: Utilities for generating embeddings.
    - fastapi: FastAPI framework for defining API routes and handling HTTP exceptions.
    - pydantic: For request validation and data modeling.
    - log_config: Custom logger for logging operations and errors.
"""

import app.config
from app.embedding import get_embedding, EmbeddingRequest
from shared.models.summarize import SummarizeRequest

from shared.log_config import get_logger
logger = get_logger(__name__)

from fastapi import HTTPException, status, APIRouter
from datetime import datetime
from dateutil.parser import isoparse
import uuid
from typing import Optional


"""
FastAPI router for handling memory-related API endpoints.

This router is used to define and organize routes related to memory search and retrieval
in the ChromaDB memory management system.
"""
router = APIRouter()


@router.post("", response_model=dict)
def add_summary(summarize_request: SummarizeRequest) -> dict:
    """
    Add a new summary to the ChromaDB collection.

    Stores the summary text with its embedding, user metadata, and generates a unique document ID.
    Supports saving summaries from different platforms for a specific user.

    Args:
        summarize_request (SummarizeRequest): Request containing summary details.

    Returns:
        dict: A dictionary with status and the generated summary ID.

    Raises:
        HTTPException: If there is an error storing the summary.
    """
    try:
        collection = app.config.client.get_or_create_collection(name=app.config.SUMMARIZE_COLLECTION)

        embedding = get_embedding(EmbeddingRequest(input=summarize_request.text))
        doc_id = f"summary-{uuid.uuid4()}"

        collection.add(
            ids=[doc_id],
            documents=[summarize_request.text],
            embeddings=[embedding],
            metadatas=[{
                "user_id": summarize_request.user_id,
                "platform": summarize_request.platform,
                "timestamp": summarize_request.timestamp
            }]
        )

        logger.info(f"📝 Stored summary {doc_id} for user {summarize_request.user_id}")
        return {
            "status": "success",
            "id": doc_id
        }

    except Exception as e:
        logger.error(f"Error adding summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add summary"
        )


@router.get("/{id}", response_model=dict)
def get_summary(id: str) -> dict:
    """
    Retrieve a specific summary by its unique identifier.

    Fetches a summary document from the ChromaDB collection using the provided ID.
    Returns the summary text and associated metadata, or raises an appropriate HTTP error
    if the summary is not found or cannot be retrieved.

    Args:
        id (str): The unique identifier of the summary to retrieve.

    Returns:
        dict: A dictionary containing the summary ID, text, and metadata.

    Raises:
        HTTPException: 404 if the summary is not found, or 500 if retrieval fails.
    """
    try:
        logger.debug(f"📥 Fetching summary with ID: {id}")
        collection = app.config.client.get_or_create_collection(name=app.config.SUMMARIZE_COLLECTION)
        results = collection.get(ids=[id], include=["documents", "metadatas"])

        if not results["documents"]:
            logger.warning(f"Summary with ID {id} not found.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Summary not found"
            )

        logger.debug(f"📤 Retrieved summary {id} with metadata: {results['metadatas'][0]}")
        return {
            "id": id,
            "text": results["documents"][0],
            "metadata": results["metadatas"][0]
        }

    except Exception as e:
        logger.error(f"Error retrieving summary {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summary"
        )


@router.get("/user/{user_id}", response_model=list)
def get_user_summary(user_id: str, since: Optional[str] = None, platform: Optional[str] = None) -> list:
    """
    Retrieve summaries for a specific user, optionally filtered by timestamp and platform.

    Args:
        user_id (str): The unique identifier of the user whose summaries are to be retrieved.
        since (Optional[str], optional): The earliest timestamp to filter summaries. Defaults to None.
        platform (Optional[str], optional): The platform to filter summaries by. Defaults to None.

    Returns:
        list: A list of summary dictionaries, each containing the summary's ID, text, and metadata.

    Raises:
        HTTPException: 500 error if retrieval of user summaries fails.
    """
    try:
        logger.debug(f"🔍 Summary filters — user_id: {user_id}, since: {since}, platform: {platform}")
        collection = app.config.client.get_or_create_collection(name=app.config.SUMMARIZE_COLLECTION)

        where_clause = {"user_id": user_id}
        if since:
            where_clause["timestamp"] = {"$gte": since.isoformat()}
        if platform:
            where_clause["platform"] = {"$contains": platform}

        results = collection.get(where=where_clause, include=["documents", "metadatas"])

        summaries = []
        for doc_id, text, metadata in zip(results["ids"], results["documents"], results["metadatas"]):
            summaries.append({
                "id": doc_id,
                "text": text,
                "metadata": metadata
            })

        logger.debug(f"📦 Retrieved {len(summaries)} summaries for user {user_id}")
        return summaries

    except Exception as e:
        logger.error(f"Error retrieving summaries for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user summaries"
        )


@router.delete("/{id}", response_model=dict)
def delete_summary(id: str) -> dict:
    """
    Delete a specific summary by its unique identifier.

    Args:
        id (str): The unique identifier of the summary to be deleted.

    Returns:
        dict: A dictionary with a status and message indicating successful deletion.

    Raises:
        HTTPException: 500 error if deletion of the summary fails.
    """
    try:
        logger.debug(f"🧼 Deletion request received for summary ID: {id}")
        collection = app.config.client.get_or_create_collection(name=app.config.SUMMARIZE_COLLECTION)

        collection.delete(ids=[id])
        logger.info(f"🗑️ Deleted summary with ID {id}")
        return {
            "status": "success",
            "message": f"Summary {id} deleted"
        }

    except Exception as e:
        logger.error(f"Error deleting summary {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete summary"
        )


@router.get("/search", response_model=list)
def search_summary(
    q: str,
    user_id: Optional[str] = None,
    platform: Optional[str] = None,
    since: Optional[str] = None
) -> list:
    """
    Search summaries with optional filtering and semantic ranking.

    Args:
        q (str): Search query text to find semantically similar summaries.
        user_id (Optional[str], optional): Filter summaries by specific user ID.
        platform (Optional[str], optional): Filter summaries by platform containing the given string.
        since (Optional[str], optional): Filter summaries created after this timestamp.

    Returns:
        list: Ranked list of matching summary documents, sorted by semantic relevance and recency.

    Raises:
        HTTPException: 500 error if search operation fails.
    """
    try:
        logger.debug(f"🔎 Search query received: '{q}' | user_id={user_id}, platform={platform}, since={since}")
        collection = app.config.client.get_or_create_collection(name=app.config.SUMMARIZE_COLLECTION)

        where_clause = {}
        if user_id:
            where_clause["user_id"] = user_id
        if platform:
            where_clause["platform"] = {"$contains": platform}
        if since:
            where_clause["timestamp"] = {"$gte": since.isoformat()}

        embedding = get_embedding(EmbeddingRequest(input=q))
        logger.debug(f"📈 Generated embedding of length {len(embedding)}")

        results = collection.query(
            query_embeddings=[embedding],
            n_results=25,
            include=["documents", "metadatas", "ids", "distances"],
            where=where_clause if where_clause else None
        )

        logger.debug(f"📥 Retrieved {len(results['ids'][0])} semantic matches")

        matches = []
        now = datetime.now().isoformat()

        for doc_id, text, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            timestamp = isoparse(metadata["timestamp"])
            age_seconds = (now - timestamp).total_seconds()

            semantic_score = 1 - distance
            recency_score = 1 / (1 + age_seconds / 3600)
            combined_score = (semantic_score * 0.7) + (recency_score * 0.3)

            matches.append({
                "id": doc_id,
                "text": text,
                "metadata": metadata,
                "score": combined_score
            })

        matches.sort(key=lambda x: x["score"], reverse=True)
        for entry in matches:
            entry.pop("score", None)

        return matches

    except Exception as e:
        logger.error(f"Error searching summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )
