"""
This module provides an API endpoint for deleting a memory entry from a ChromaDB collection by its unique identifier.

Routes:
    DELETE /memory/{memory_id}:
        Deletes a memory entry with the specified ID from the ChromaDB collection.
        - Returns 204 No Content on successful deletion.
        - Returns 404 if the memory entry is not found.
        - Returns 500 for internal server or database errors.

Dependencies:
    - get_collection: Dependency to retrieve the ChromaDB collection.
    - get_logger: Logger for error and event logging.

Exceptions:
    - HTTPException: Raised for not found (404) and internal errors (500).
"""
from app.memory.util import get_collection

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from fastapi import HTTPException, status, APIRouter, Depends, Response
router = APIRouter()


@router.delete("/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a memory by ID")
async def memory_delete(memory_id: str, collection = Depends(get_collection)):
    """
    Delete a memory entry from the ChromaDB collection by its unique identifier.

    Args:
        memory_id (str): The unique identifier of the memory to be deleted.

    Raises:
        HTTPException: 404 if the memory is not found, or 500 for internal server or database errors.

    Returns:
        Response: A 204 No Content response indicating successful deletion.
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
