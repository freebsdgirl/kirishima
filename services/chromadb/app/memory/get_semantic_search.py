"""
Provides an API endpoint for performing semantic search on memory records stored in ChromaDB.

This module defines a FastAPI router with a single GET endpoint `/memory/semantic` that allows clients to perform
semantic searches over memory records using embedding similarity, with optional metadata-based filtering. The endpoint
supports filtering by component, mode, and priority, and allows limiting the number of results returned. The search
results are sorted by semantic relevance, priority, and timestamp.

Key Functions:
- memory_semantic_search: Handles GET requests for semantic memory search, embedding the query, applying filters,
    querying ChromaDB, and returning results as a list of MemoryView objects.

Dependencies:
- FastAPI for API routing and dependency injection
- Pydantic for data validation
- ChromaDB for vector search
- Custom modules for embedding and logging

Raises:
- HTTPException: For errors in embedding generation, ChromaDB query failures, or unexpected response payloads.
"""

from app.memory.util import get_collection
from app.embedding import get_embedding

from shared.models.memory import MemorySearch, MemoryView
from shared.models.embedding import EmbeddingRequest

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from pydantic import ValidationError

from typing import List, Optional

from fastapi import HTTPException, status, APIRouter, Depends, Query
router = APIRouter()


@router.get("/memory/semantic", response_model=List[MemoryView], summary="Semantic search memories with optional metadata filters")
async def memory_semantic_search(
    text: str = Query(...),
    component: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    priority: Optional[float] = Query(None),
    limit: Optional[int] = Query(None),
    collection = Depends(get_collection)
) -> List[MemoryView]:
    """
    Perform a semantic search on memories with optional metadata filtering.

    Retrieves memories from ChromaDB using semantic embedding similarity and optional metadata constraints.
    Supports filtering by component, mode, and priority, with configurable result limit.

    Args:
        text (str): Query text to semantically search memories
        component (Optional[str]): Filter memories by specific component
        mode (Optional[str]): Filter memories by specific mode
        priority (Optional[float]): Filter memories by priority (0-1 range)
        limit (Optional[int]): Maximum number of results to return

    Returns:
        List[MemoryView]: Matching memory records, sorted and truncated as specified
    """

    logger.debug(f"/memory/semantic GET Request:\n{text=}, {component=}, {mode=}, {priority=}, {limit=}")

    filters = []
    if component is not None:
        filters.append({"component": component})
    if mode is not None:
        filters.append({"mode": mode})
    if priority is not None:
        filters.append({"priority": priority})

    # compose the 'where' clause
    if len(filters) == 0:
        where = None
    elif len(filters) == 1:
        # just one condition, no need for $and
        where = filters[0]
    else:
        # multiple conditions => wrap in $and
        where = {"$and": filters}

    # 2) Embed the query text
    try:
        query_emb = get_embedding(EmbeddingRequest(input=text))
    except Exception as e:
        logger.error(f"Error generating query embedding: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating query embedding: {e}"
        )

    # 3) Run the ChromaDB semantic query
    try:
        if where is None:
            results = collection.query(
                query_embeddings=[query_emb],
                include=["documents", "embeddings", "metadatas", "distances"],
            )
        else:
            results = collection.query(
                query_embeddings=[query_emb],
                include=["documents", "embeddings", "metadatas", "distances"],
                where=where
            )

    except Exception as e:
        logger.error(f"ChromaDB semantic query failed: {e}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ChromaDB semantic query failed: {e}"
        )

    # 4) Unpack and build view models (truncating embeddings)
    try:
        ids        = results["ids"]
        docs       = results["documents"]
        embs       = results["embeddings"]
        metadatas  = results["metadatas"]
        distances  = results["distances"]

    except KeyError as e:
        logger.error(f"Unexpected ChromaDB payload (missing {e.args[0]})")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected ChromaDB payload (missing {e.args[0]})"
        )

    items: List[MemoryView] = []
    # Flatten all found entries for each query result
    for _id, doc, emb, meta, dist in zip(ids, docs, embs, metadatas, distances):
        # Each of these is a list (possibly empty) of results for the query
        for i in range(len(_id)):
            try:
                view = MemoryView(
                    id=_id[i],
                    memory=doc[i],
                    embedding=emb[i],  # <-- include embedding here
                    metadata=meta[i],
                    distance=dist[i],
                )
            except ValidationError:
                logger.error(f"Invalid record skipped.")
                continue
            items.append(view)

    # 5) Sort by relevance (distance asc), then priority (desc), then timestamp (desc)
    def sort_key(v):
        # Lower distance is more relevant
        # Higher priority is more important (default 0)
        # Newer timestamp is more important (ISO8601, so lexicographic sort works)
        prio = v.metadata.priority if hasattr(v.metadata, 'priority') and v.metadata.priority is not None else 0
        ts = v.metadata.timestamp if hasattr(v.metadata, 'timestamp') and v.metadata.timestamp is not None else ''
        return (v.distance if v.distance is not None else float('inf'), -prio, ts)
    items.sort(key=sort_key)

    # 6) apply limit
    if limit is not None:
        items = items[:limit]

    return items
