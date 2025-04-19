import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from shared.models.chromadb import MemoryEntryFull, MemoryListQuery, SemanticSearchQuery

import httpx
from fastapi import APIRouter, HTTPException, status, Depends

router = APIRouter()


@router.get("/memory", response_model=list[MemoryEntryFull])
async def list_memory(query: MemoryListQuery = Depends()):
    """
    List all memory entries for a specific component and/or mode.

    Args:
        query (MemoryListQuery): The query parameters for listing memory entries.

    Returns:
        list[MemoryEntryFull]: A list of memory entries matching the criteria.

    Raises:
        HTTPException: If there are issues retrieving the memory entries from ChromaDB.
    """
    logger.debug(f"/memory/list Request:\n{query.model_dump_json(indent=4)}")

    try:
        chromadb_host, chromadb_port = shared.consul.get_service_address('chromadb')
        if not chromadb_host or not chromadb_port:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB service is unavailable."
            )

        async with httpx.AsyncClient() as client:
            params = query.dict(exclude_none=True)
            # Remove 'limit' from params sent to ChromaDB if present
            limit = params.pop('limit', None)
            response = await client.get(
                f"http://{chromadb_host}:{chromadb_port}/memory",
                params=params
            )

            response.raise_for_status()
            json_response = response.json()
            # Only include entries with a non-empty embedding
            entries = [MemoryEntryFull(**entry) for entry in json_response if entry.get("embedding") and len(entry["embedding"]) > 0]
            # Apply limit if specified
            if limit is not None:
                try:
                    limit = int(limit)
                    entries = entries[:limit]
                except Exception:
                    pass
            return entries

    except httpx.RequestError as req_err:
        logger.exception("Request error while listing memory: %s", req_err)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ChromaDB service is unavailable."
        )

    except Exception as err:
        logger.exception("Unexpected error while listing memory: %s", err)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing memory."
        )


@router.get("/memory/semantic", response_model=list[MemoryEntryFull])
async def search_semantic(query: SemanticSearchQuery = Depends()):
    """
    Perform a semantic search on memory entries.

    Args:
        query (SemanticSearchQuery): The semantic search query parameters.

    Returns:
        list[MemoryEntryFull]: A list of memory entries matching the semantic search criteria.

    Raises:
        HTTPException: If there are issues retrieving memory entries from ChromaDB or if the service is unavailable.
    """
    logger.debug(f"/memory/semantic Request:\n{query.model_dump_json(indent=4)}")

    try:
        chromadb_host, chromadb_port = shared.consul.get_service_address('chromadb')

        if not chromadb_host or not chromadb_port:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB service is unavailable."
            )

        params = query.model_dump(exclude_none=True)
        params['text'] = params.pop('search')

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{chromadb_host}:{chromadb_port}/memory/semantic",
                params=params
            )
            response.raise_for_status()
            json_response = response.json()
            return [MemoryEntryFull(**entry) for entry in json_response if entry.get("embedding") and len(entry["embedding"]) > 0]
    
    except httpx.RequestError as req_err:
        logger.exception("Request error while performing semantic search: %s", req_err)
    
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ChromaDB service is unavailable."
        )

    except Exception as err:
        logger.exception("Unexpected error during semantic search: %s", err)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during semantic search."
        )
