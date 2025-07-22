from shared.models.ledger import CanonicalUserMessage, TopicMessagesRequest

from app.util import _open_conn

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from typing import List
import json


def _get_topic_messages(request: TopicMessagesRequest) -> List[CanonicalUserMessage]:
    """
    Helper function to get messages for a specific topic.
    """
    topic_id = request.topic_id
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE topic_id = ? ORDER BY id", (topic_id,))
        columns = [col[0] for col in cur.description]
        raw_messages = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        # Parse JSON fields if needed
        for msg in raw_messages:
            if msg.get("tool_calls"):
                try:
                    msg["tool_calls"] = json.loads(msg["tool_calls"])
                except Exception:
                    msg["tool_calls"] = None
            if msg.get("function_call"):
                try:
                    msg["function_call"] = json.loads(msg["function_call"])
                except Exception:
                    msg["function_call"] = None
        
        messages = [CanonicalUserMessage(**msg) for msg in raw_messages]
        # Filter out tool messages and assistant messages with empty content
        messages = [
            msg for msg in messages
            if not (
                getattr(msg, 'role', None) == 'tool' or
                (getattr(msg, 'role', None) == 'assistant' and not getattr(msg, 'content', None))
            )
        ]
        return messages