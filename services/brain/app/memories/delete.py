"""
This module provides an API endpoint for deleting memory entries from the database by their unique ID.

Functions:
    memory_delete(memory_id: str) -> dict:
        Deletes a memory entry from the database using the provided memory ID.
        - Accepts the memory ID as a query parameter.
        - Loads the database configuration from a JSON file.
        - Connects to the SQLite database and attempts to delete the memory entry.
        - Returns a status dictionary upon successful deletion.
        - Raises HTTPException with status 404 if the memory ID does not exist.
        - Raises HTTPException with status 500 for any internal errors.
        - Logs all request, success, and failure events for debugging purposes.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
import json

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()

@router.delete("/memories/delete", response_model=dict)
def memory_delete(
    memory_id: str = Query(..., description="The ID of the memory to delete.")
):
    """
    Deletes a memory entry from the database by its ID.

    Args:
        memory_id (str): The ID of the memory to delete. Provided as a query parameter.

    Returns:
        dict: A dictionary containing the status of the deletion and the ID of the deleted memory.

    Raises:
        HTTPException: 
            - 404 Not Found: If no memory with the specified ID exists.
            - 500 Internal Server Error: If an error occurs during the deletion process.

    Logs:
        - Logs the incoming request, success, and failure cases for debugging purposes.
    """
    logger.debug(f"DELETE /memories/delete Request: memory_id={memory_id}")
    # Load config to get the memories DB path
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            if cursor.rowcount == 0:
                logger.debug(f"Memory ID {memory_id} not found for deletion.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No memory found with that ID."
                )
        logger.debug(f"Memory ID {memory_id} deleted successfully.")
        return {"status": "memory deleted", "id": memory_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting memory: {str(e)}"
        )