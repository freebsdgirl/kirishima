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
