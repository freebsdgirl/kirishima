
import app.config as config

from shared.log_config import get_logger
logger = get_logger(f"contacts.{__name__}")

import os
import sqlite3

def initialize_database():
    """
    Initialize the contacts database with required schema if it does not exist.
    
    Creates the necessary SQLite database tables for contacts, including contacts, 
    aliases, and fields tables. Ensures the database directory exists and sets up 
    foreign key constraints. Logs the initialization process.
    """
    schema = '''
    CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS aliases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id TEXT NOT NULL,
        alias TEXT NOT NULL,
        UNIQUE(contact_id, alias),
        FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        UNIQUE(contact_id, key),
        FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
    );
    '''
    db_path = config.CONTACTS_DB
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    needs_init = not os.path.exists(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        # Check if tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'")
        contacts_exists = cursor.fetchone() is not None
        if needs_init or not contacts_exists:
            logger.info("Initializing contacts database with schema.")
            conn.executescript(schema)
        else:
            logger.info("Contacts database already initialized.")