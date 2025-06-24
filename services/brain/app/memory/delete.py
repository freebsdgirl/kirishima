"""
This module provides an API endpoint for deleting a specific memory entry from ChromaDB.

It defines a FastAPI router with a DELETE endpoint at "/memory" that accepts a MemoryEntry object.
The endpoint attempts to find and delete the first memory entry matching the provided memory content and mode.
If successful, it returns the ID of the deleted memory. If no matching memory is found, it returns a 404 error.
If the ChromaDB service is unavailable or an error occurs during the deletion process, appropriate HTTP exceptions are raised.

Dependencies:
- shared.config.TIMEOUT: Timeout configuration for HTTP requests.
- shared.consul: Service discovery for ChromaDB.
- shared.models.memory.MemoryEntry: Pydantic model for memory entries.
- shared.log_config.get_logger: Logger configuration.
- httpx: For asynchronous HTTP requests.
- fastapi: For API routing and exception handling.
"""

import shared.consul

from shared.models.memory import MemoryEntry

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import json

from fastapi import APIRouter, HTTPException, status, Body
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.delete("/memory", response_model=dict, status_code=200)
async def delete_memory(request: MemoryEntry = Body(...)):
    """
    Delete a specific memory entry from ChromaDB based on memory content and mode.

    Attempts to find and delete the first memory entry matching the provided memory and mode.
    Returns the id of the deleted memory if found and deleted, or 404 if not found.
    Raises an HTTPException if the ChromaDB service is unavailable or if there are errors during the deletion process.

    Args:
        request (MemoryEntry): The memory entry to be deleted, containing memory content and mode.

    Raises:
        HTTPException: If ChromaDB service is unavailable or deletion fails.
    """
    logger.debug(f"/memory DELETE Request: memory={request.memory}, mode={request.mode}")

    try:
        chromadb_host, chromadb_port = shared.consul.get_service_address('chromadb')
        if not chromadb_host or not chromadb_port:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB service is unavailable."
            )

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"http://{chromadb_host}:{chromadb_port}/memory",
                params={"mode": request.mode}
            )

            if response.status_code != status.HTTP_200_OK:
                logger.error(f"Failed to search memories: {response.status_code} {response.text}")

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to search for memories."
                )
            memories = response.json()

            matches = [m for m in memories if m["memory"] == request.memory and m["metadata"]["mode"] == request.mode]

            if not matches:
                logger.info("No matching memories found to delete.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No matching memory found to delete."
                )

            # Only delete the first match
            m = matches[0]
            mem_id = m["id"]
            del_resp = await client.delete(f"http://{chromadb_host}:{chromadb_port}/memory/{mem_id}")

            if del_resp.status_code != status.HTTP_204_NO_CONTENT:
                logger.error(f"Failed to delete memory id={mem_id}: {del_resp.status_code} {del_resp.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete memory id={mem_id}."
                )
            return {"id": mem_id}

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"An error occurred while deleting memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting memory: {e}"
        )
