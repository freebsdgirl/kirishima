"""
This module provides an API endpoint for assigning a topic to user messages within a specified timestamp range.

Functions:
    _assign_messages_to_topic(body: AssignTopicRequest) -> int:
        Helper function to update the topic_id of user messages in the database for a given time range.

    assign_topic_to_messages(body: AssignTopicRequest):
        FastAPI route handler for PATCH /topics/{topic_id}.
        Validates input, checks topic existence, ensures messages exist in the given timeframe,
        and assigns the topic to matching messages.

    HTTPException: For invalid input, non-existent topics, or if no messages are found/updated.

    dict: Number of updated messages, e.g., {"updated": <rowcount>}.
"""
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")
from shared.models.ledger import AssignTopicRequest
from app.util import _open_conn
from app.topic.util import topic_exists, _validate_timestamp
from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _assign_messages_to_topic(body: AssignTopicRequest) -> int:
    """
    Assigns a topic to all user messages within a specified time range.

    Args:
        topic_id (str): The ID of the topic to assign.
        start (str): The start timestamp in the format 'YYYY-MM-DD HH:MM:SS[.sss]'.
        end (str): The end timestamp in the format 'YYYY-MM-DD HH:MM:SS[.sss]'.

    Returns:
        int: The number of updated messages.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_messages SET topic_id = ? WHERE created_at >= ? AND created_at <= ?",
            (body.topic_id, body.start, body.end)
        )
        conn.commit()
        return cur.rowcount


@router.patch("/topics/{topic_id}")
def assign_topic_to_messages(
    body: AssignTopicRequest
):
    """
    FastAPI route handler for assigning a topic to user messages within a specified timestamp range.
    
    Validates input by checking:
    - Topic existence
    - Timestamp format and validity
    - Start time is before end time
    - Messages exist in the given timeframe
    
    Raises:
        HTTPException: For invalid input, non-existent topics, or if no messages are found/updated.
    
    Returns:
        dict: Number of updated messages, e.g., {"updated": <rowcount>}.
    """
    logger.debug(f"Assigning topic {body.topic_id} to messages from {body.start} to {body.end}")
    if not topic_exists(body.topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    if not body.start or not body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start and end times must be provided.")
    if not _validate_timestamp(body.start) or not _validate_timestamp(body.end):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timestamp format. Use ISO 8601 format.")
    if body.start >= body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be before end time.")
    start = _validate_timestamp(body.start)
    end = _validate_timestamp(body.end)
    if not topic_exists(body.topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    with _open_conn() as conn:
        cur = conn.cursor()
        # check to see if there are any messages in the given timeframe
        cur.execute(
            "SELECT COUNT(*) FROM user_messages WHERE created_at >= ? AND created_at <= ?",
            (start, end)
        )
        count = cur.fetchone()[0]
        if count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No messages found in the given timeframe.")
        updated_count = _assign_messages_to_topic(body.topic_id, start, end)
        if updated_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No messages found to update.")
    logger.debug(f"Updated {updated_count} messages with topic {body.topic_id}")
    # Return the number of updated messages
    if updated_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No messages found to update.")
    return {"updated": updated_count}
