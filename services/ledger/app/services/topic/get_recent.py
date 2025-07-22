
from app.util import _open_conn

from shared.models.ledger import TopicResponse, TopicRecentRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from typing import List

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
