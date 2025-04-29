"""
This module provides an API endpoint for adding memory entries to a ChromaDB collection.
It defines a FastAPI router with a POST endpoint `/memory` that accepts a `MemoryEntry` object,
generates an embedding if not provided, validates the entry, and stores it in the ChromaDB collection.
The endpoint handles errors related to embedding generation, validation, and storage, and returns
the fully processed and stored memory entry as a `MemoryEntryFull` object.
Dependencies:
    - FastAPI
    - ChromaDB collection dependency
    - Embedding generation utility
    - Shared logging and model definitions
Endpoints:
    - POST /memory: Add a memory entry to the ChromaDB collection.
"""
from app.memory.util import get_collection
from app.embedding import get_embedding

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.chromadb import MemoryEntry, MemoryMetadata, MemoryEntryFull
from shared.models.embedding import EmbeddingRequest

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.post("/memory", response_model=MemoryEntryFull)
async def memory_add(request_data: MemoryEntry, collection = Depends(get_collection)):
    """
    Handles the POST request to add a memory entry to the ChromaDB collection.

    Validates the input memory entry, generates embeddings if not provided, and stores the entry
    in the ChromaDB collection. Supports automatic embedding generation and handles various
    validation and storage errors.

    Args:
        request_data (MemoryEntry): The memory entry to be added.
        collection (ChromaDB Collection): The ChromaDB collection to store the memory entry.

    Returns:
        MemoryEntryFull: The fully processed and stored memory entry.

    Raises:
        HTTPException: For embedding generation errors, validation issues, or ChromaDB storage problems.
    """
    logger.debug(f"/memory POST Request:\n{request_data.model_dump_json(indent=4)}")

    emb = request_data.embedding
    if emb is None:
        try:
            emb = get_embedding(EmbeddingRequest(input=request_data.memory))

        except Exception as e:
            logger.error(f"ERROR getting embedding: {e}")

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Embedding error: {e}"
            )

    try:
        data = request_data.model_dump()

        memory_entry = MemoryEntryFull(
            memory=data['memory'],
            embedding=emb,
            metadata=MemoryMetadata(
                priority=data['priority'],
                component=data['component'],
                mode=data['mode']
            )
        )

        logger.debug(f"Memory Entry:\n{memory_entry.model_dump_json(indent=4)}")

    except Exception as e:
        logger.error(f"ERROR validating memory entry: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ERROR validating memory entry: {e}"
        )

    try:
        meta_dict = memory_entry.metadata.model_dump()
        collection.add(
            ids       = [memory_entry.id],
            documents = [memory_entry.memory],
            embeddings= [memory_entry.embedding],
            metadatas = [meta_dict],
        )

    except Exception as e:
        logger.error(f"ERROR adding memory entry to ChromaDB: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB error: {e}"
        )
        
    logger.info(f"Memory added with ID: {memory_entry.id}")

    return memory_entry
