from app.config import BUFFER_DB

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3

# SQL schema for buffer table and summary metadata
SCHEMA_SQL = """
-- 1‑on‑1 message buffer
CREATE TABLE IF NOT EXISTS user_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT    NOT NULL,
    platform        TEXT    NOT NULL,
    platform_msg_id TEXT,
    role            TEXT    NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content         TEXT    NOT NULL,
    model           TEXT,
    tool_calls      TEXT,
    function_call   TEXT,
    created_at      DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime')),
    updated_at      DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_user_msgs_order
    ON user_messages(user_id, id);

--------------------------------------------------------------------

-- Group‑chat buffer (Discord channels / threads)
CREATE TABLE IF NOT EXISTS conversation_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT    NOT NULL,
    platform        TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('user','assistant','system')),
    content         TEXT    NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime')),
    updated_at      DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_convo_msgs_order
    ON conversation_messages(conversation_id, id);

--------------------------------------------------------------------

-- User‑level summaries (multi‑level compression)
CREATE TABLE IF NOT EXISTS user_summaries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             TEXT    NOT NULL,
    content             TEXT    NOT NULL,
    level               INTEGER NOT NULL,   -- 1, 2, 3, …
    timestamp_begin     TEXT    NOT NULL,
    timestamp_end       TEXT    NOT NULL,
    timestamp_summarized TEXT   NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_user_summaries_level
    ON user_summaries(user_id, level, id);

--------------------------------------------------------------------

-- Conversation summaries (daily → weekly → monthly)
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id     TEXT    NOT NULL,
    content             TEXT    NOT NULL,
    period              TEXT    NOT NULL CHECK (period IN ('daily','weekly','monthly')),
    timestamp_begin     TEXT    NOT NULL,
    timestamp_end       TEXT    NOT NULL,
    timestamp_summarized TEXT   NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_conv_summaries_period
    ON conversation_summaries(conversation_id, period, id);
"""


def init_buffer_db():
    """
    Initialize the buffer database by creating the messages table and required indexes.
    
    This function connects to the buffer database, executes the predefined schema SQL script,
    commits the changes, and closes the database connection.
    """
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()