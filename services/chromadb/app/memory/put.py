"""
This module provides an endpoint for replacing an entire memory entry in ChromaDB by its unique identifier.

Endpoints:
    PUT /memory/{memory_id}:
        - Replaces an existing memory entry with new data.
        - Validates the existence of the memory entry.
        - Generates an embedding if not provided.
        - Validates the new memory entry data.
        - Updates the memory entry in ChromaDB.
        - Returns a truncated view of the updated memory entry.

Dependencies:
    - FastAPI for API routing and HTTP exception handling.
    - Pydantic for data validation.
    - ChromaDB collection for memory storage.
    - Embedding service for generating embeddings.
    - Shared models for memory and embedding data structures.
    - Logger for error reporting.
"""

from app.memory.util import get_collection
from app.embedding import get_embedding

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.memory import MemoryEntry, MemoryMetadata, MemoryEntryFull, MemoryView
from shared.models.embedding import EmbeddingRequest

from pydantic import ValidationError

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.put("/memory/{memory_id}", response_model=MemoryView, summary="Replace an entire memory by ID")
async def memory_put(memory_id: str, request_data: MemoryEntry,collection = Depends(get_collection)) -> MemoryView:
    """
    Replace an entire memory entry by its unique identifier.

    Args:
        memory_id (str): The unique identifier of the memory to be replaced.
        request_data (MemoryEntry): The new memory entry data.

    Returns:
        MemoryView: The updated memory entry with its new details.

    Raises:
        HTTPException: 404 if the memory is not found, 400 for validation errors,
                    or 500 for internal server or database errors.
    """
    # 1) ensure it exists
    try:
        existing = collection.get(ids=[memory_id])

    except Exception as e:
        logger.error(f"ChromaDB lookup failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB lookup failed: {e}"
        )

    if not existing.get("ids"):
        logger.error(f"Memory with id={memory_id} not found")

        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id={memory_id} not found"
        )

    # 2) ensure we have an embedding
    emb = request_data.embedding
    if emb is None:
        try:
            emb = get_embedding(EmbeddingRequest(input=request_data.memory))

        except Exception as e:
            logger.error(f"ERROR generating embedding: {e}")

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating embedding: {e}"
            )

    # 3) build & validate full entry (new timestamp)
    try:
        full = MemoryEntryFull(
            id=memory_id,
            memory=request_data.memory,
            embedding=emb,
            metadata=MemoryMetadata(
                priority=request_data.priority,
                component=request_data.component,
            )
        )

    except ValidationError as e:
        logger.error(f"ERROR validating memory entry: {e}")

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e}"
        )

    # 4) push update to ChromaDB
    try:
        collection.update(
            ids=[full.id],
            documents=[full.memory],
            embeddings=[full.embedding],
            metadatas=[full.metadata.model_dump()]
        )

    except Exception as e:
        logger.error(f"ChromaDB update failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB update failed: {e}"
        )

    # 5) return truncated view
    return MemoryView(
        id=full.id,
        memory=full.memory,
        embedding=[full.embedding[0]] if full.embedding else [],
        metadata=full.metadata
    )
