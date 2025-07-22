from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

from fastapi import HTTPException, status

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