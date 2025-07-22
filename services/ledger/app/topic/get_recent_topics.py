"""
This module provides an API endpoint to retrieve a list of recent topics based on user messages.
Functions:
    _get_recent_topics(limit: int = 5):
        Helper function to fetch recent, distinct, non-null topic IDs from the 'user_messages' table,
        ordered by 'created_at' in descending order, and returns their corresponding names from the 'topics' table.
API Endpoints:
    GET /topics:
        Returns a list of recent topics, each represented as a TopicResponse with 'id' and 'name'.
        The number of topics returned can be controlled via the 'limit' query parameter.
    - Topics are determined from the 'user_messages' table.
    - Topics are ordered by recency based on the 'created_at' timestamp.
"""
from fastapi import APIRouter, Query
from typing import List
from app.util import _open_conn
from shared.models.ledger import TopicResponse, TopicRecentRequest
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

router = APIRouter()


def _get_recent_topics(request: TopicRecentRequest) -> List[TopicResponse]:
    """
    Helper function to get recent topics.
    """
    limit = request.limit if request.limit is not None else 5
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT topic_id FROM user_messages WHERE topic_id IS NOT NULL ORDER BY created_at DESC"
        )
        topic_ids = []
        seen = set()
        for row in cur.fetchall():
            tid = row[0]
            if tid and tid not in seen:
                topic_ids.append(tid)
                seen.add(tid)
            if len(topic_ids) >= limit:
                break
        topics = []
        for tid in topic_ids:
            cur.execute("SELECT name FROM topics WHERE id = ?", (tid,))
            result = cur.fetchone()
            if result:
                topics.append(TopicResponse(id=tid, name=result[0]))
        return topics


@router.get("/topics/_recent", response_model=List[TopicResponse])
def get_recent_topics(
    limit: int = Query(5, description="Number of recent topics to return (ordered by recency)"),
):
    """
    Retrieve a list of recent topics.

    Args:
        limit (int, optional): Number of recent topics to return. Defaults to 5.

    Returns:
        List[TopicResponse]: A list of topic response objects, each containing the 'id' and 'name' of a recent topic.

    Notes:
        - Topics are determined from the 'user_messages' table, ordered by 'created_at' in descending order.
        - Only distinct, non-null topic IDs are considered.
    """
    request = TopicRecentRequest(limit=limit)
    return _get_recent_topics(request)