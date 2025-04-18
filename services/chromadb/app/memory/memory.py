"""
This module provides FastAPI routes for managing memory entries in a ChromaDB collection.
It includes endpoints for adding, deleting, updating, and partially updating memory entries.
The module also handles embedding generation, validation, and error handling for memory operations.
Routes:
    - POST /memory: Add a new memory entry to the ChromaDB collection.
    - DELETE /memory/{memory_id}: Delete a memory entry by its ID.
    - PUT /memory/{memory_id}: Replace an entire memory entry by its ID.
    - PATCH /memory/{memory_id}: Partially update a memory entry by its ID.
Dependencies:
    - `get_collection`: Dependency to retrieve the ChromaDB collection instance.
Models:
    - MemoryEntry: Input model for memory entries.
    - MemoryEntryFull: Full representation of a memory entry, including metadata and embedding.
    - MemoryMetadata: Metadata associated with a memory entry.
    - MemoryView: Truncated view of a memory entry for responses.
    - MemoryPatch: Model for partial updates to a memory entry.
    - EmbeddingRequest: Model for embedding generation requests.
Exceptions:
    - HTTPException: Raised for validation errors, embedding generation issues, or ChromaDB operation failures.
Utilities:
    - `get_embedding`: Function to generate embeddings for memory entries.
    - `get_logger`: Function to configure and retrieve a logger instance.
Notes:
    - The module uses Pydantic for data validation and FastAPI for routing and dependency injection.
    - Logging is implemented to track requests, errors, and operations.
"""

from app.embedding import get_embedding
import app.memory.setup

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.chromadb import MemoryEntry, MemoryMetadata, MemoryEntryFull, MemoryView, MemoryPatch
from shared.models.embedding import EmbeddingRequest

from pydantic import ValidationError

from fastapi import HTTPException, status, APIRouter, Depends, Response
router = APIRouter()


async def get_collection():
    """
    Asynchronously retrieves the ChromaDB collection instance.
    
    Returns:
        ChromaDB Collection: The configured ChromaDB collection for memory storage.
    """
    return app.memory.setup.collection()


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
            emb = get_embedding(request_data.memory)

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


@router.delete(
    "/memory/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory by ID"
)
async def memory_delete(
    memory_id: str,
    collection = Depends(get_collection),
):
    """
    Delete a specific memory entry by its unique identifier.

    Args:
        memory_id (str): The unique identifier of the memory to be deleted.

    Returns:
        Response: A 204 No Content response if deletion is successful.

    Raises:
        HTTPException: 404 if the memory is not found, or 500 if a database error occurs.
    """
    """
    Deletes the memory with the given ID.
    Returns 204 No Content on success, or 404 if not found.
    """
    # 1) Check existence
    try:
        res = collection.get(ids=[memory_id])

    except Exception as e:
        logger.error(f"ChromaDB lookup failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB lookup failed: {e}"
        )

    if not res.get("ids"):
        logger.error(f"Memory with id={memory_id} not found")

        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id={memory_id} not found"
        )

    # 2) Perform deletion
    try:
        collection.delete(ids=[memory_id])

    except Exception as e:
        logger.error(f"ChromaDB deletion failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB deletion failed: {e}"
        )

    # 3) Return 204 No Content
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/memory/{memory_id}",
    response_model=MemoryView,
    summary="Replace an entire memory by ID"
)
async def memory_put(
    memory_id: str,
    request_data: MemoryEntry,
    collection = Depends(get_collection),
):
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


@router.patch(
    "/memory/{memory_id}",
    response_model=MemoryView,
    summary="Partially update a memory by ID"
)
async def memory_patch(
    memory_id: str,
    patch: MemoryPatch,
    collection = Depends(get_collection),
):
    """
    Partially update a memory entry by its ID.

    Allows updating memory content, embedding, priority, or component. If memory is changed
    and no new embedding is provided, a new embedding will be automatically generated.
    The original timestamp is preserved during the update.

    Args:
        memory_id (str): Unique identifier of the memory to update
        patch (MemoryPatch): Partial update details for the memory
        collection: ChromaDB collection for storing memories

    Returns:
        MemoryView: Updated memory entry with truncated view
    """
    # 1) fetch existing record
    try:
        res = collection.get(ids=[memory_id])

    except Exception as e:
        logger.error(f"ChromaDB lookup failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB lookup failed: {e}"
        )

    if not res.get("ids"):
        logger.error(f"Memory with id={memory_id} not found")

        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id={memory_id} not found"
        )

    old_doc      = res["documents"][0]
    old_emb      = res["embeddings"][0] or []
    old_meta_raw = res["metadatas"][0]

    # parse old metadata into model
    try:
        old_meta = MemoryMetadata.model_validate(old_meta_raw)

    except ValidationError as e:
        logger.error(f"Bad metadata in DB: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bad metadata in DB: {e}"
        )

    # 2) apply patches
    new_doc   = patch.memory    or old_doc
    new_comp  = patch.component or old_meta.component
    new_pri   = patch.priority  if patch.priority is not None else old_meta.priority

    # embedding: regenerate if memory changed & no new embedding provided
    if patch.embedding is not None:
        new_emb = patch.embedding
    elif patch.memory is not None:
        try:
            new_emb = get_embedding(EmbeddingRequest(input=new_doc))

        except Exception as e:
            logger.error(f"ERROR re-generating embedding: {e}")

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error re-generating embedding: {e}"
            )
    else:
        new_emb = old_emb

    # preserve original timestamp
    new_meta = MemoryMetadata(
        timestamp=old_meta.timestamp,
        priority=new_pri,
        component=new_comp
    )

    # 3) build & validate full entry
    try:
        full = MemoryEntryFull(
            id=memory_id,
            memory=new_doc,
            embedding=new_emb,
            metadata=new_meta
        )

    except ValidationError as e:
        logger.error(f"ERROR validating memory entry: {e}")

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e}"
        )

    # 4) push update
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