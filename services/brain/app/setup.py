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
import app.config

import sqlite3
from pathlib import Path


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
    # Check the database path, return if it exists
    db_path = Path(app.config.STATUS_DB)

    if db_path.exists():
        return

    # Create the directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to (or create) the SQLite database
    with sqlite3.connect(app.config.STATUS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("CREATE TABLE IF NOT EXISTS status (key, value)")
        cursor.execute("INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",("mode", "default"))
        cursor.execute("CREATE TABLE IF NOT EXISTS notifications (user_id TEXT, notification TEXT, timestamp TEXT)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON notifications (user_id)")
        cursor.execute("CREATE TABLE IF NOT EXISTS last_seen (user_id TEXT, last_seen TEXT)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON last_seen (user_id)")

        # Commit and close
        conn.commit()