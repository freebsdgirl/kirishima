from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import Request

from app.util import _open_conn
from shared.log_config import get_logger
from shared.models.ledger import CanonicalUserMessage


logger = get_logger(f"ledger.{__name__}")

_CONFIG_PATH = os.getenv("LEDGER_CONFIG_PATH", "/app/config/config.json")


def _get_single_user_id() -> str:
    with open(_CONFIG_PATH) as f:
        config = json.load(f)
    user_id = config.get("user_id")
    if not user_id:
        raise ValueError("Missing required 'user_id' in ledger config")
    return str(user_id)


def _fetch_new_messages(conn, user_id: str, last_seen_id: int) -> list[CanonicalUserMessage]:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM user_messages WHERE user_id = ? AND id > ? ORDER BY id ASC",
        (user_id, last_seen_id),
    )
    colnames = [desc[0] for desc in cur.description]
    messages: list[CanonicalUserMessage] = []
    for row in cur.fetchall():
        msg = dict(zip(colnames, row))
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
        messages.append(CanonicalUserMessage(**msg))
    return messages


def _sse_event(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def _to_json(model: CanonicalUserMessage) -> str:
    if hasattr(model, "model_dump_json"):
        return model.model_dump_json()
    return model.json()


async def _stream_user_message_events(
    request: Request, poll_ms: int = 250, heartbeat_s: float = 15.0
) -> AsyncIterator[str]:
    user_id = _get_single_user_id()
    conn = _open_conn()

    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM user_messages WHERE user_id = ?", (user_id,))
        last_seen_id = int(cur.fetchone()[0] or 0)
        last_heartbeat = time.monotonic()

        while True:
            if await request.is_disconnected():
                break

            new_messages = _fetch_new_messages(conn, user_id, last_seen_id)
            if new_messages:
                for message in new_messages:
                    yield _sse_event("message", _to_json(message))
                    last_seen_id = message.id
                last_heartbeat = time.monotonic()

            now = time.monotonic()
            if now - last_heartbeat >= heartbeat_s:
                heartbeat = json.dumps({"ts": datetime.now(timezone.utc).isoformat()})
                yield _sse_event("heartbeat", heartbeat)
                last_heartbeat = now

            await asyncio.sleep(poll_ms / 1000)

    except asyncio.CancelledError:
        logger.info("Ledger user stream cancelled by client disconnect.")
        raise
    finally:
        conn.close()
