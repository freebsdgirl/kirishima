
from app.util import _open_conn

from shared.models.ledger import TopicResponse

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from typing import List


def _get_all_topics() -> List[TopicResponse]:
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