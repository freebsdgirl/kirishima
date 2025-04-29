"""
This module provides an API endpoint for partially updating a memory entry in a ChromaDB collection.

It defines a FastAPI router with a PATCH endpoint `/memory/{memory_id}` that allows updating specific fields
of a memory entry, such as memory content, embedding, priority, or component. If the memory content is changed
and no new embedding is provided, a new embedding is automatically generated. The original timestamp is preserved
during the update process. The endpoint performs validation, handles errors, and returns a truncated view of the
updated memory entry.

Dependencies:
    - FastAPI
    - Pydantic
    - ChromaDB collection interface
    - Embedding generation utility
    - Shared logging and model definitions

Endpoints:
    - PATCH /memory/{memory_id}: Partially update a memory entry by its ID.
"""

from app.memory.util import get_collection
from app.embedding import get_embedding

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.memory import MemoryPatch, MemoryMetadata, MemoryEntryFull, MemoryView
from shared.models.embedding import EmbeddingRequest

from pydantic import ValidationError

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.patch("/memory/{memory_id}", response_model=MemoryView, summary="Partially update a memory by ID")
async def memory_patch(memory_id: str, patch: MemoryPatch, collection = Depends(get_collection)) -> MemoryView:
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
        res = collection.get(ids=[memory_id], include=["embeddings", "metadatas", "documents"])

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
    old_emb      = res["embeddings"][0]
    if old_emb is None:
        old_emb = []
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
    new_mode  = patch.mode      or old_meta.mode
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
        component=new_comp,
        mode=new_mode
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