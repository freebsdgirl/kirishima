from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from shared.models.ledger import MergeTopicsRequest

from app.util import _open_conn

from typing import Dict


def _merge_topics(request: MergeTopicsRequest) -> Dict:
    """
    Merge multiple topics into a primary topic.
    
    This function:
    1. Updates the primary topic name if provided
    2. Moves all memory-topic associations from merge topics to primary topic
    3. Deletes the old topics
    
    Args:
        request (MergeTopicsRequest): The merge request model.
    
    Returns:
        Dict with merge results including moved memories and deleted topics
    """
    primary_id = request.primary_id
    primary_name = request.primary_name
    merge_ids = request.merge_ids
    if not merge_ids:
        return {
            "primary_topic_id": primary_id,
            "primary_topic_name": primary_name,
            "deleted_topics": [],
            "moved_memories": 0
        }
    conn = _open_conn()
    cursor = conn.cursor()
    moved_memories = 0
    deleted_topics = []
    try:
        # Update primary topic name if provided and different
        if primary_name:
            cursor.execute("UPDATE topics SET name = ? WHERE id = ?", (primary_name, primary_id))
            logger.info(f"Updated primary topic {primary_id} name to '{primary_name}'")
        # Move memories from merge topics to primary topic
        for topic_id in merge_ids:
            # Move memory-topic associations
            cursor.execute("""
                UPDATE memory_topics 
                SET topic_id = ? 
                WHERE topic_id = ?
            """, (primary_id, topic_id))
            moved_count = cursor.rowcount
            moved_memories += moved_count
            if moved_count > 0:
                logger.info(f"Moved {moved_count} memory associations from topic {topic_id} to {primary_id}")
            # Delete the old topic
            cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            if cursor.rowcount > 0:
                deleted_topics.append(topic_id)
                logger.info(f"Deleted topic {topic_id}")
        conn.commit()
        logger.info(f"Successfully merged {len(merge_ids)} topics into {primary_id}, moved {moved_memories} memory associations")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error merging topics: {e}")
        raise
    finally:
        conn.close()
    return {
        "primary_topic_id": primary_id,
        "primary_topic_name": primary_name,
        "deleted_topics": deleted_topics,
        "moved_memories": moved_memories
    }
