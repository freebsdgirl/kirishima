from shared.models.ledger import ToolSyncRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

import json

TABLE = "user_messages"


def _sync_tool_buffer_helper(request: ToolSyncRequest):
    """
    Args:
        request: ToolSyncRequest containing tool_call, tool_output, and tool_call_id
    """

    with open('/app/config/config.json') as f:
            _config = json.load(f)
    # if turns isn't set, default to 15
    user_id = _config.get("user_id")

    with _open_conn() as conn:
        cur = conn.cursor()
        # first, insert the tool call
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, model, platform, role, tool_calls, tool_call_id) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, request.model, request.platform, "assistant", request.tool_call, request.tool_call_id),
        )
        # then, insert the tool output
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, model, platform, role, content, tool_call_id) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, request.model, request.platform, "tool", request.tool_output, request.tool_call_id),
        )
        conn.commit()
