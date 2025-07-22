"""
This module sets up the SQLite database schema for the ledger service, including tables for user messages,
user-level summaries, and topics. It provides a function to initialize the buffer database by creating
the necessary tables and indexes as defined in the SCHEMA_SQL.
Functions:
    init_buffer_db():
        Initializes the buffer database by executing the schema SQL script, which creates tables and indexes
        for message buffering, user summaries, and topics. Reads the database path from a configuration file.
"""
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3
import json

# SQL schema for buffer table and summary metadata
SCHEMA_SQL = """
-- message buffer
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
    topic_id        TEXT REFERENCES topics(id) ON DELETE SET NULL, -- Foreign key with cascading
    created_at      DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime')),
    updated_at      DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_user_msgs_order
    ON user_messages(user_id, id);
CREATE INDEX IF NOT EXISTS idx_user_msgs_topic
    ON user_messages(topic_id);

--------------------------------------------------------------------


-- Topics table
CREATE TABLE IF NOT EXISTS topics (
    id          TEXT PRIMARY KEY, -- UUID
    name        TEXT,
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);


--------------------------------------------------------------------

-- Summaries table
CREATE TABLE IF NOT EXISTS summaries (
    id                  TEXT PRIMARY KEY, -- UUID
    summary             TEXT,
    timestamp_begin     DATETIME NOT NULL,
    timestamp_end       DATETIME NOT NULL,
    summary_type        TEXT
);
CREATE INDEX IF NOT EXISTS idx_summaries_type_time
    ON summaries(summary_type, timestamp_begin, timestamp_end);
CREATE INDEX IF NOT EXISTS idx_summaries_time
    ON summaries(timestamp_begin, timestamp_end);


--------------------------------------------------------------------

-- Memories table
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    memory TEXT,
    created_at TEXT,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    reviewed INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_created_at ON memories (created_at);
CREATE INDEX IF NOT EXISTS idx_last_accessed ON memories (last_accessed);


CREATE TABLE IF NOT EXISTS memory_tags (
    memory_id TEXT,
    tag TEXT,
    PRIMARY KEY (memory_id, tag),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_memory_id ON memory_tags (memory_id);
CREATE INDEX IF NOT EXISTS idx_tag ON memory_tags (tag);


CREATE TABLE IF NOT EXISTS memory_category (
    memory_id TEXT,
    category TEXT,
    PRIMARY KEY (memory_id, category),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_memory_id ON memory_category (memory_id);
CREATE INDEX IF NOT EXISTS idx_category ON memory_category (category);


CREATE TABLE IF NOT EXISTS memory_topics (
    memory_id TEXT REFERENCES memories(id) ON DELETE CASCADE,
    topic_id TEXT REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (memory_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_memory_topics_memory_id ON memory_topics (memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_topics_topic_id ON memory_topics (topic_id);


--------------------------------------------------------------------

-- Heatmap tables for dynamic keyword relevance tracking
CREATE TABLE IF NOT EXISTS heatmap_score (
    keyword TEXT PRIMARY KEY,
    score REAL NOT NULL,
    last_updated DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_heatmap_score_value ON heatmap_score (score);
CREATE INDEX IF NOT EXISTS idx_heatmap_last_updated ON heatmap_score (last_updated);


CREATE TABLE IF NOT EXISTS heatmap_memories (
    memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    score REAL NOT NULL,
    last_updated DATETIME NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_heatmap_memories_score ON heatmap_memories (score);
CREATE INDEX IF NOT EXISTS idx_heatmap_memories_updated ON heatmap_memories (last_updated);
"""


def init_buffer_db():
    """
    Initialize the buffer database by creating the messages table and required indexes.
    
    This function connects to the buffer database, executes the predefined schema SQL script,
    commits the changes, and closes the database connection.
    """

    with open('/app/config/config.json') as f:
        _config = json.load(f)

        db = _config["db"]["ledger"]
    conn = sqlite3.connect(db, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()