from shared.models.ledger import TopicIDsTimeframeRequest

from app.util import _open_conn
from app.services.topic.util import _validate_timestamp
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from typing import List


def _get_topic_ids_in_timeframe(body: TopicIDsTimeframeRequest) -> List[str]:
    start = _validate_timestamp(body.start)
    end = _validate_timestamp(body.end)
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT topic_id FROM user_messages WHERE created_at >= ? AND created_at <= ? AND topic_id IS NOT NULL",
            (start, end)
        )
        return [row[0] for row in cur.fetchall()]