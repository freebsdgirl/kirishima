"""
This module provides an API endpoint for performing exact-match searches on memory documents stored in a ChromaDB collection.
Routes:
    GET /memory/search:
        - Performs an exact-match search for memory entries whose text matches the provided query.
        - Returns a list of matching MemoryView objects, sorted by timestamp in descending order.
        - Supports optional limiting of the number of results.
        - Returns 404 if no matches are found.
Dependencies:
    - get_collection: Dependency to retrieve the ChromaDB collection.
    - MemoryView: Pydantic model representing a memory entry.
    - get_logger: Logger for request and error logging.
    - HTTPException: For ChromaDB lookup failures, unexpected payloads, or no matches found.
"""
from app.memory.util import get_collection

from shared.models.memory import MemoryView

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from pydantic import ValidationError
from typing import List, Optional

from fastapi import HTTPException, status, APIRouter, Depends, Query
router = APIRouter()


@router.get(
"/memory/search",
    response_model=List[MemoryView],
    summary="Exact‑match search on the memory text",
    responses={
        404: {"description": "No memory entries found matching the given text"}
    }
)
async def memory_search(
    text: str = Query(..., description="Exact document text to match"),
    limit: Optional[int] = Query(None, ge=1, description="Max number of entries to return"),
    collection=Depends(get_collection),
):
    """
    Perform an exact-match search on memory documents.

    Retrieves memory entries that exactly match the given text, with optional result limiting.
    Returns a sorted list of matching MemoryView objects, ordered by timestamp in descending order.

    Args:
        text (str): The exact document text to match against stored memories.
        limit (Optional[int], optional): Maximum number of entries to return. Defaults to None.
        collection: ChromaDB collection to search within.

    Returns:
        List[MemoryView]: Matching memory entries, sorted by timestamp.

    Raises:
        HTTPException: If ChromaDB lookup fails or returns an unexpected payload.
    """
    logger.debug(f"/memory/search GET Request: {text}")
    # 1) fetch everything (no semantic search)
    try:
        results = collection.get(include=["documents", "embeddings", "metadatas"])

    except Exception as e:
        logger.error(f"ChromaDB lookup failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB lookup failed: {e}"
        )

    # 2) unpack
    try:
        ids        = results["ids"]
        documents  = results["documents"]
        embeddings = results["embeddings"]
        metadatas  = results["metadatas"]

    except KeyError as e:
        logger.error(f"ChromaDB returned unexpected payload (missing {e.args[0]})")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB returned unexpected payload (missing {e.args[0]})"
        )

    # 3) filter exact matches, truncate embeddings, build view models
    items: List[MemoryView] = []
    for _id, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
        if doc != text:
            continue
        if emb is None or len(emb) == 0:
            continue  # skip if somehow no embedding

        truncated = [emb[0]]

        try:
            view = MemoryView(
                id=_id,
                memory=doc,
                embedding=truncated,
                metadata=meta
            )

        except ValidationError:
            logger.error(f"Invalid record skipped.")
            continue

        items.append(view)

    # 4) sort by timestamp descending
    items.sort(key=lambda v: v.metadata.timestamp, reverse=True)

    # 5) apply limit
    if limit is not None:
        items = items[:limit]
    
    # 6) if still empty, return 404
    if not items:
        logger.debug(f"No memory entries found matching '{text}'")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No memory entries found matching '{text}'"
        )

    return items
