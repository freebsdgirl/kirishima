"""
This module provides an API endpoint for deleting topics from the database.
It defines a FastAPI router with a DELETE endpoint at "/topics/{topic_id}".
The endpoint checks if the topic exists, deletes it if found, and returns the number of deleted topics.
If the topic does not exist or has already been deleted, a 404 HTTP error is raised.
Functions:
    _delete_topic(topic_id: str): Helper function to delete a topic by its ID.
    delete_topic(topic_id: str): FastAPI endpoint to handle topic deletion requests.
"""
from app.util import _open_conn
from app.topic.util import topic_exists
from fastapi import APIRouter, HTTPException, status
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

router = APIRouter()


def _delete_topic(topic_id: str):
    """
    Helper function to delete a topic from the database by its ID.
    
    Args:
        topic_id (str): The unique identifier of the topic to delete.
    
    Returns:
        int: The number of deleted topics (should be 1 if successful).
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()
        return cur.rowcount


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    deleted_count = _delete_topic(topic_id)
    if deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found or already deleted.")
    return {"deleted": deleted_count}