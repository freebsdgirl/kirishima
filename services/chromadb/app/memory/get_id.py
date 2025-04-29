"""
This module provides an endpoint for retrieving a single memory entry from a ChromaDB collection by its unique identifier.

Functions:
    memory_get(memory_id: str, collection = Depends(get_collection)) -> MemoryView:
        FastAPI GET endpoint to fetch a memory by ID. Returns a MemoryView containing the document, a truncated embedding (first element only), and metadata.
        Handles errors for missing entries, ChromaDB lookup failures, and response validation issues.
"""
from app.memory.util import get_collection

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.chromadb import MemoryView

from pydantic import ValidationError

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.get("/memory/id/{memory_id}", response_model=MemoryView, summary="Fetch a single memory by ID (truncated embedding)")
async def memory_get(memory_id: str, collection = Depends(get_collection)) -> MemoryView:
    """
    Retrieve a single memory by its unique identifier.

    Args:
        memory_id (str): The unique identifier of the memory to retrieve.
        collection: ChromaDB collection to query.

    Returns:
        MemoryView: A memory entry with its document, truncated embedding, and metadata.

    Raises:
        HTTPException: If the memory is not found or if there's an error during retrieval.
    """

    logger.debug(f"/memory/id/{memory_id} GET Request")

    try:
        results = collection.get(
            ids=[memory_id],
            include=["documents", "embeddings", "metadatas"]
        )

    except Exception as e:
        logger.error(f"ChromaDB lookup failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB lookup failed: {e}"
        )

    ids = results.get("ids", [])
    if not ids:
        logger.debug(f"Memory with id={memory_id} not found")

        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id={memory_id} not found"
        )

    # 2) pull out the raw list of embeddings (a list of arrays/lists)
    emb_list = results.get("embeddings")

    if emb_list is None:
        emb_list = []

    # 3) safely grab the first vector (or None)
    first_vec = emb_list[0] if len(emb_list) > 0 else None

    # 4) check its length, not its truthiness
    if first_vec is None or len(first_vec) == 0:
        # missing or empty → either truncate to [] or regenerate…
        truncated = []
    else:
        truncated = [ first_vec[0] ]

    try:
        view = MemoryView(
            id=memory_id,
            memory=results["documents"][0],
            embedding=truncated,
            metadata=results["metadatas"][0],
        )

    except ValidationError as e:
        logger.error(f"Response validation error: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response validation error: {e}"
        )

    logger.debug(f"Memory View:\n{view.model_dump_json(indent=4)}")

    return view
