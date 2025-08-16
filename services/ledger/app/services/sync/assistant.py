from shared.models.ledger import AssistantSyncRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

import json

TABLE = "user_messages"


def _sync_assistant_buffer_helper(request: AssistantSyncRequest):
    """
    Args:
        request: AssistantSyncRequest containing assistant message content
    """

    with open('/app/config/config.json') as f:
            _config = json.load(f)
    # if turns isn't set, default to 15
    user_id = _config.get("user_id")

    with _open_conn() as conn:
        cur = conn.cursor()
        
        # Check the last message to ensure it's not an assistant message with content
        cur.execute(
            f"SELECT role, content FROM {TABLE} WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        last_row = cur.fetchone()
        
        if last_row:
            last_role, last_content = last_row
            if last_role == "assistant" and last_content:
                raise ValueError("Cannot insert assistant message: previous message is already an assistant message with content")
        
        # Insert the assistant message
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, model, platform, role, content) VALUES (?, ?, ?, ?, ?)",
            (user_id, request.model, request.platform, "assistant", request.content),
        )
        conn.commit()
