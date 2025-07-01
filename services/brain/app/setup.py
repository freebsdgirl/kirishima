"""
This module provides functionality to verify and initialize the application's SQLite database.
Functions:
    verify_database():
        Checks if the application's SQLite database exists at the configured path.
        - If the database does not exist, creates the necessary directory structure.
        - Initializes the database with required tables:
            - status: Stores key-value configuration settings.
            - notifications: Tracks user notifications with timestamps.
            - last_seen: Tracks user last seen timestamps.
        - Sets up indexes for efficient querying.
        - Configures the database to use Write-Ahead Logging (WAL) for improved performance.
"""

import sqlite3
from pathlib import Path
import json

def verify_database():
    """
    Verify and initialize the application's SQLite database.
    
    This function checks if the database file exists, creates the necessary directory,
    and sets up the required tables and indexes if they do not already exist. 
    Specifically, it creates tables for:
    - status: Stores key-value configuration settings
    - notifications: Tracks user notifications with timestamp
    - last_seen: Tracks user last seen timestamps
    
    The database is configured with WAL (Write-Ahead Logging) journal mode for improved performance.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    if _config['db']['brainlets']:
        brainlets_db_path = Path(_config['db']['brainlets'])
        # Always ensure the directory exists
        brainlets_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Always connect and ensure table/indexes exist
        with sqlite3.connect(_config['db']['brainlets']) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("CREATE TABLE IF NOT EXISTS topic_tracker (id TEXT PRIMARY KEY, user_id TEXT, topic TEXT, timestamp_begin TEXT)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON topic_tracker (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_topic ON topic_tracker (topic)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp_begin ON topic_tracker (timestamp_begin)")
            cursor.execute("CREATE TABLE IF NOT EXISTS prompt (id TEXT PRIMARY KEY, user_id TEXT, prompt TEXT, reasoning TEXT, timestamp TEXT, enabled BOOLEAN DEFAULT 1)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_user_id ON prompt (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_enabled ON prompt (enabled)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_timestamp ON prompt (timestamp)")
            conn.commit()

    if _config['db']['status']:
        status_db_path = Path(_config['db']['status'])
        if not status_db_path.exists():
            # Create the directory if it doesn't exist
            status_db_path.parent.mkdir(parents=True, exist_ok=True)

            # Connect to (or create) the SQLite database
        with sqlite3.connect(_config['db']['status']) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("CREATE TABLE IF NOT EXISTS notifications (id TEXT, user_id TEXT, notification TEXT, timestamp TEXT, status TEXT)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON notifications (user_id)")
            cursor.execute("CREATE TABLE IF NOT EXISTS last_seen (user_id TEXT, platform TEXT, timestamp TEXT)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON last_seen (user_id)")
            
            # Commit and close
            conn.commit()

    # now check for the memories database
    if _config['db']['memories']:
        memories_db_path = Path(_config['db']['memories'])
        if not memories_db_path.exists():
            # Create the directory if it doesn't exist
            memories_db_path.parent.mkdir(parents=True, exist_ok=True)
            # Connect to (or create) the memories SQLite database
        with sqlite3.connect(_config['db']['memories']) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, user_id TEXT, memory TEXT, created_at TEXT, access_count INTEGER DEFAULT 0, last_accessed TEXT, priority FLOAT, reviewed INTEGER DEFAULT 0)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON memories (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON memories (created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON memories (priority)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON memories (last_accessed)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_tags (
                    memory_id TEXT,
                    tag TEXT,
                    PRIMARY KEY (memory_id, tag),
                    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_id ON memory_tags (memory_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag ON memory_tags (tag)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_category (
                    memory_id TEXT,
                    category TEXT,
                    PRIMARY KEY (memory_id, category),
                    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_id ON memory_category (memory_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON memory_category (category)")

            # create table to map memory ids to topic ids
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_topics (
                    memory_id TEXT,
                    topic_id TEXT,
                    PRIMARY KEY (memory_id, topic_id),
                    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_id ON memory_topics (memory_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_topic_id ON memory_topics (topic_id)")   
            # Commit and close
            conn.commit()