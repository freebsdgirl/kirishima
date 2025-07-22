from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from shared.models.ledger import AssignTopicRequest

from app.util import _open_conn
from app.services.topic.util import _topic_exists, _validate_timestamp

from fastapi import HTTPException, status


def _assign_messages_to_topic(body: AssignTopicRequest) -> dict:
    """
    Validates input and assigns a topic to all user messages within a specified time range.
    Returns a dict: {"updated": <rowcount>} or raises HTTPException.
    """
    logger.debug(f"Assigning topic {body.topic_id} to messages from {body.start} to {body.end}")
    if not _topic_exists(body.topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    if not body.start or not body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start and end times must be provided.")
    if not _validate_timestamp(body.start) or not _validate_timestamp(body.end):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timestamp format. Use ISO 8601 format.")
    if body.start >= body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be before end time.")
    start = _validate_timestamp(body.start)
    end = _validate_timestamp(body.end)
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
        # update messages
        cur.execute(
            "UPDATE user_messages SET topic_id = ? WHERE created_at >= ? AND created_at <= ?",
            (body.topic_id, start, end)
        )
        updated_count = cur.rowcount
        conn.commit()
    logger.debug(f"Updated {updated_count} messages with topic {body.topic_id}")
    if updated_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No messages found to update.")
    return {"updated": updated_count}