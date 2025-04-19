"""
This module provides FastAPI endpoints for managing and querying memory entries stored in a ChromaDB collection.
It includes functionalities for retrieving individual memories, listing memories with optional filters, performing
exact-match searches, and conducting semantic searches with metadata constraints.
Endpoints:
    - GET /memory/{memory_id}: Retrieve a single memory by its unique identifier.
    - GET /memory: Fetch a list of memories with optional filtering and pagination.
    - GET /memory/search: Perform an exact-match search on memory documents.
    - GET /memory/semantic: Conduct a semantic search on memories with optional metadata filters.
Dependencies:
    - ChromaDB collection setup is handled by `app.memory.setup`.
    - Embedding generation is provided by `app.embedding.get_embedding`.
    - Logging is configured using `shared.log_config.get_logger`.
Models:
    - MemoryView: Represents a memory entry with its document, truncated embedding, and metadata.
    - MemoryQuery: Defines query parameters for filtering memories.
    - EmbeddingRequest: Used for generating embeddings for semantic search.
Error Handling:
    - Returns appropriate HTTP status codes and error messages for issues such as missing records,
      validation errors, or unexpected payloads from ChromaDB.
Utilities:
    - Metadata filters (`where` clauses) are dynamically constructed based on query parameters.
    - Embeddings are truncated to include only the first element for response optimization.
    - Results are sorted by timestamp in descending order where applicable.
"""

from app.embedding import get_embedding
import app.memory.setup

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.chromadb import MemoryView, MemoryQuery
from fastapi import Query
from shared.models.embedding import EmbeddingRequest

from fastapi import HTTPException, status, APIRouter, Depends
from typing import List, Optional
from pydantic import ValidationError

router = APIRouter()


async def get_collection():
    """
    Asynchronously retrieves the ChromaDB collection instance.
    
    Returns:
        ChromaDB Collection: The configured ChromaDB collection for memory storage.
    """
    return app.memory.setup.collection()


@router.get(
    "/memory/id/{memory_id}",
    response_model=MemoryView,
    summary="Fetch a single memory by ID (truncated embedding)"
)
async def memory_get(memory_id: str, collection = Depends(get_collection)):
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


@router.get(
    "/memory",
    response_model=List[MemoryView],
    summary="Fetch memories matching any combination of component/mode/priority"
)
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
    
    print(f"THE LIMIT DOES NOT EXIST: {limit}")
    # 6) if still empty, return 404
    if not items:
        logger.debug(f"No memory entries found matching '{text}'")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No memory entries found matching '{text}'"
        )

    return items


@router.get(
    "/memory/semantic",
    response_model=List[MemoryView],
    summary="Semantic search memories with optional metadata filters"
)
async def memory_semantic_search(
    text: str = Query(..., description="Query text for semantic search"),
    component: Optional[str]  = Query(None, description="Filter by component"),
    mode:      Optional[str]  = Query(None, description="Filter by mode"),
    priority:  Optional[float]= Query(None, ge=0, le=1, description="Filter by priority"),
    limit:     Optional[int]  = Query(None, ge=1, description="Max number of results"),
    collection = Depends(get_collection),
):
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

    logger.debug(f"/memory/semantic GET Request:\n{text}")

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

    # 3) Run the ChromaDB semantic querypr
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
        embs       = results["embeddings"]  # <-- add this line
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

    print(f"THE SEMANTIC LIMIT DOES NOT EXIST: {limit}")
    # 6) apply limit
    if limit is not None:
        items = items[:limit]

    return items
