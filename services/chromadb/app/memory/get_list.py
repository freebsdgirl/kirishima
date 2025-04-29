"""
This module provides an API endpoint for retrieving a list of memory entries from a ChromaDB collection,
with optional filtering by component, mode, and priority. The endpoint supports pagination via a limit
parameter and returns results sorted by timestamp (descending) and priority (descending). Each memory
entry is returned as a `MemoryView` object, including truncated embeddings and associated metadata.

Key Features:
- FastAPI router with a `/memory` GET endpoint.
- Supports filtering by component, mode, and priority using query parameters.
- Results are sorted by timestamp and priority, and can be limited in count.
- Handles ChromaDB collection queries and error reporting.
- Returns a list of validated `MemoryView` objects.
"""

from app.memory.util import get_collection

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.memory import MemoryView, MemoryQuery
from fastapi import Query

from fastapi import HTTPException, status, APIRouter, Depends
from typing import List, Optional
from pydantic import ValidationError

router = APIRouter()


@router.get("/memory", response_model=List[MemoryView], summary="Fetch memories matching any combination of component/mode/priority")
async def memory_list(
    q:     MemoryQuery                  = Depends(),
    limit: Optional[int]                = Query(None, ge=1, description="Max number of entries to return"),
    collection                          = Depends(get_collection),
):
    """
    Retrieve a list of memories with optional filtering and pagination.

    Allows querying memories by component, mode, and priority. Returns memories sorted
    by timestamp in descending order, with optional limit on the number of results.

    Args:
        q: Query parameters for filtering memories
        limit: Maximum number of memory entries to return
        collection: ChromaDB collection to query

    Returns:
        List of MemoryView objects matching the query criteria
    """

    logger.debug(f"/memory GET Request:\n{q.model_dump_json(indent=4)}")

    # build your individual filters
    filters = []
    if q.component is not None:
        filters.append({"component": q.component})
    if q.mode is not None:
        filters.append({"mode": q.mode})
    if q.priority is not None:
        filters.append({"priority": q.priority})

    # compose the 'where' clause
    if len(filters) == 0:
        where = None
    elif len(filters) == 1:
        # just one condition, no need for $and
        where = filters[0]
    else:
        # multiple conditions => wrap in $and
        where = {"$and": filters}

    # compose the 'where' clause
    if len(filters) == 0:
        where = None
    elif len(filters) == 1:
        # just one condition, no need for $and
        where = filters[0]
    else:
        # multiple conditions => wrap in $and
        where = {"$and": filters}

    include = ["documents", "embeddings", "metadatas"]

    try:
        # If we have any filter, pass it; otherwise, fetch all without `where`
        if where is None:
            results = collection.get(include=include)
        else:
            results = collection.get(where=where, include=include)

    except Exception as e:
        logger.error(f"ChromaDB lookup failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB lookup failed: {e}"
        )

    # 2) Unpack parallel lists
    try:
        ids       = results["ids"]
        docs      = results["documents"]
        embs      = results["embeddings"]
        metadatas = results["metadatas"]

    except KeyError as e:
        logger.error(f"ChromaDB returned unexpected payload (missing {e.args[0]})")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB returned unexpected payload (missing {e.args[0]})"
        )

    # 3) Assemble & truncate embeddings
    items: List[MemoryView] = []
    for _id, doc, emb, meta in zip(ids, docs, embs, metadatas):
    # emb might be a numpy array or list—check its length explicitly
        if emb is None or len(emb) == 0:
            continue

        # safe to grab first element now
        truncated = [emb[0]]
        # we assume `meta` already has component, mode, priority, timestamp fields
        try:
            view = MemoryView(
                id=_id,
                memory=doc,
                embedding=truncated,
                metadata=meta,
            )

        except ValidationError as ve:
            # log & skip malformed records
            logger.error(f"Invalid record skipped: {ve}")
            continue

        items.append(view)

    # 4) Sort by timestamp descending, then by priority descending
    # If timestamp is ISO8601 string, lexicographic sort works for timestamp
    # For priority, higher values are more important (descending)
    items.sort(key=lambda v: (v.metadata.timestamp, v.metadata.priority if v.metadata.priority is not None else 0), reverse=True)
    # 5) Apply limit if given

    if limit is not None:
        items = items[:limit]

    return items


