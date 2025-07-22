from shared.models.ledger import CanonicalUserMessage, UserMessagesRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from app.services.user.util import _get_period_range

from app.util import _open_conn

import sqlite3
from typing import List
from datetime import datetime, timedelta
import json


def _get_user_messages(request: UserMessagesRequest) -> List[CanonicalUserMessage]:
    """
    Internal helper to retrieve messages for a specific user, optionally filtered by time period, date, or explicit start/end timestamps.
    
    Args:
        request: UserMessagesRequest containing filtering parameters
        
    Returns:
        List[CanonicalUserMessage]: Filtered user messages
    """
    user_id = request.user_id
    period = request.period
    date = request.date
    start = request.start
    end = request.end
    
    logger.debug(f"Fetching messages for user {user_id} (date={date}, period={period}, start={start}, end={end})")

    # Default date logic
    if period and not date:
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            date = now.strftime("%Y-%m-%d")

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["ledger"]

    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE user_id = ? ORDER BY id", (user_id,))
        columns = [col[0] for col in cur.description]
        raw_messages = [dict(zip(columns, row)) for row in cur.fetchall()]
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
        # Remove tool/function call fields from returned messages
        for msg in messages:
            if hasattr(msg, 'tool_calls'):
                msg.tool_calls = None
            if hasattr(msg, 'function_call'):
                msg.function_call = None
        # New: filter by start/end if provided
        if start and end:
            try:
                # Accept 'YYYY-MM-DD HH:MM:SS.sss' (to milliseconds)
                start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S.%f")
                end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S.%f")
            except Exception:
                raise ValueError("Invalid start or end timestamp format. Use 'YYYY-MM-DD HH:MM:SS.sss'.")
            def parse_created_at(dt_str):
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
            messages = [
                msg for msg in messages
                if start_dt <= parse_created_at(msg.created_at) <= end_dt
            ]
        elif period:
            start_dt, end_dt = _get_period_range(period, date)
            def parse_created_at(dt_str):
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
            messages = [
                msg for msg in messages
                if start_dt <= parse_created_at(msg.created_at) <= end_dt
            ]
        return messages