"""
Module for retrieving topic IDs within a specified time frame from user messages.
This module defines an API endpoint and helper functions to query the database for distinct topic IDs
associated with user messages created between given start and end timestamps. The endpoint validates
the input timestamps, ensures they are in the correct format, and returns a list of topic IDs or
appropriate HTTP errors if the request is invalid or no topics are found.
Functions:
    _get_topic_ids_in_timeframe(body: TopicIDsTimeframeRequest) -> List[str]:
        Retrieves distinct topic IDs from user messages within the specified time frame.
API Endpoints:
    POST /topics/ids:
        Returns a list of topic IDs for messages within the provided start and end timestamps.
        Validates input and returns HTTP errors for invalid requests or empty results.
"""
from shared.models.ledger import TopicIDsTimeframeRequest
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")
from app.util import _open_conn
from app.topic.util import _validate_timestamp
from fastapi import APIRouter, HTTPException, status
from typing import List

router = APIRouter()


def _get_topic_ids_in_timeframe(body: TopicIDsTimeframeRequest) -> List[str]:
    """
    Helper function to retrieve topic IDs within a specified time frame.
    
    Args:
        start (str): Start timestamp in ISO format.
        end (str): End timestamp in ISO format.

    Returns:
        List[str]: A list of distinct topic IDs found in user messages between the start and end timestamps.
    """
    start = _validate_timestamp(body.start)
    end = _validate_timestamp(body.end)
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT topic_id FROM user_messages WHERE created_at >= ? AND created_at <= ? AND topic_id IS NOT NULL",
            (start, end)
        )
        return [row[0] for row in cur.fetchall()]


@router.post("/topics/_by-timeframe", response_model=List[str])
def get_topic_ids_in_timeframe(body: TopicIDsTimeframeRequest):
    """
    API endpoint to retrieve topic IDs within a specified time frame.

    Args:
        body (TopicIDsTimeframeRequest): Request body containing 'start' and 'end' timestamps.

    Returns:
        List[str]: A list of topic IDs that have messages within the specified time frame.
    """

    if body.start >= body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be before end time.")
    if not body.start or not body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start and end times must be provided.")
    if not _validate_timestamp(body.start) or not _validate_timestamp(body.end):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timestamp format. Use ISO 8601 format.")
    topic_ids = _get_topic_ids_in_timeframe(body)
    if not topic_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No topics found in the specified time frame.")
    return topic_ids