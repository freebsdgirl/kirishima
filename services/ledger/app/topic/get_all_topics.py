"""
This module provides an API endpoint to retrieve all topics from the database.
Functions:
    _get_all_topics():
        Helper function to fetch all topics from the database, returning a list of dictionaries
        with 'id' and 'name' for each topic.
    get_all_topics():
        FastAPI route handler for GET /topics. Returns all topics as a list of dictionaries,
"""
from fastapi import APIRouter
from typing import List
from app.util import _open_conn
from shared.models.ledger import TopicResponse
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

router = APIRouter()


def _get_all_topics():
    """
    Helper function to retrieve all topics from the database.

    Returns:
        List[TopicResponse]: A list of topic response objects, each containing the 'id' and 'name' of a topic.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM topics ORDER BY name")
        rows = cur.fetchall()
        return [TopicResponse(id=row[0], name=row[1]) for row in rows]
    

@router.get("/topics", response_model=List[TopicResponse])
def get_all_topics():
    """
    Retrieve all topics from the database.

    Returns:
        List[TopicResponse]: A list of topic response objects, each containing the 'id' and 'name' of a topic,
        ordered alphabetically by name.
    """
    return _get_all_topics()