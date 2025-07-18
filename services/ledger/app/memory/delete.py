"""
This module provides functionality to delete memory entries from the database in the ledger service.

It defines a FastAPI router with an endpoint to delete a memory by its unique ID. The deletion process includes:
- Checking if the memory exists before attempting deletion.
- Removing the memory entry from the database.
- Handling errors such as memory not found or internal server errors.
- Logging relevant events and errors for observability.

Functions:
    _memory_delete(memory_id: str): Helper function to perform the database deletion.
    memory_delete(memory_id: str): FastAPI endpoint to handle HTTP DELETE requests for memory deletion.

Dependencies:
    - shared.log_config.get_logger: For logging.
    - app.memory.util.memory_exists: To check existence of a memory entry.
    - app.util._open_conn: For database connection management.
    - fastapi.APIRouter, HTTPException, status: For API routing and error handling.
"""
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.memory.util import memory_exists
from app.util import _open_conn

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


def _memory_delete(memory_id: str):
    """
    Helper function to delete a memory entry from the database by its ID.

    Args:
        memory_id (str): The unique identifier of the memory to delete.
    """
    with _open_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No memory found with that ID."
            )


@router.delete("/memories/by-id/{memory_id}", response_model=dict)
def memory_delete(memory_id: str):
    """
    Deletes a memory entry from the database by its ID.

    Args:
        memory_id (str): The ID of the memory to delete. Provided as a path parameter.

    Returns:
        dict: A dictionary containing the status of the deletion and the ID of the deleted memory.

    Raises:
        HTTPException: 
            - 404 Not Found: If no memory with the specified ID exists.
            - 500 Internal Server Error: If an error occurs during the deletion process.
    """
    logger.debug(f"DELETE /memories/{{id}} Request")

    if not memory_exists(memory_id):
        logger.error(f"Memory with ID {memory_id} not found.")
        return {"status": "error", "message": "Memory not found."}
    try:
        _memory_delete(memory_id)
        logger.info(f"Memory with ID {memory_id} deleted successfully.")
        return {"status": "success", "deleted_memory_id": memory_id}
    except HTTPException as e:
        logger.error(f"Error deleting memory with ID {memory_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Internal server error while deleting memory with ID {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while deleting the memory."
        )