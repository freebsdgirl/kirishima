"""
Database utilities for Google Contacts caching.

This module provides functions for managing a local SQLite cache of Google Contacts
to minimize API calls and improve performance.

Functions:
    get_db_path(): Gets the database path from configuration.
    init_contacts_db(): Initializes the contacts database schema.
    get_db_connection(): Gets a database connection.
    cache_contact(): Caches a single contact in the database.
    cache_contacts(): Caches multiple contacts in the database.
    get_cached_contact_by_email(): Retrieves a cached contact by email address.
    get_all_cached_contacts(): Retrieves all cached contacts.
    clear_contacts_cache(): Clears all cached contacts.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

from app.services.gmail.util import get_config

import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime


def get_db_path() -> str:
    """
    Get the database path from configuration.
    
    Returns:
        str: The path to the contacts cache database
    """
    config = get_config()
    return config.get('db', {}).get('googleapi_contacts', './shared/db/googleapi/contacts.db')


def get_db_connection() -> sqlite3.Connection:
    """
    Get a database connection with proper configuration.
    
    Returns:
        sqlite3.Connection: Database connection with foreign keys enabled
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_contacts_db():
    """
    Initialize the contacts database schema.
    
    Creates the necessary tables for caching Google Contacts data.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create contacts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                resource_name TEXT PRIMARY KEY,
                etag TEXT,
                display_name TEXT,
                given_name TEXT,
                family_name TEXT,
                middle_name TEXT,
                raw_data TEXT,  -- JSON storage for complete contact data
                cached_at TEXT,
                modified_at TEXT
            )
        ''')
        
        # Create contact emails table for fast email lookups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_name TEXT,
                email TEXT,
                email_type TEXT,
                is_primary BOOLEAN DEFAULT 0,
                FOREIGN KEY (resource_name) REFERENCES contacts (resource_name) ON DELETE CASCADE
            )
        ''')
        
        # Create indices for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contact_emails_email ON contact_emails (email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contact_emails_resource ON contact_emails (resource_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contacts_display_name ON contacts (display_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contacts_cached_at ON contacts (cached_at)')
        
        conn.commit()
        logger.info("Contacts database initialized successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing contacts database: {e}")
        raise
    finally:
        conn.close()


def cache_contact(contact_data: Dict[str, Any]):
    """
    Cache a single contact in the database.
    
    Args:
        contact_data: The contact data from Google People API
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Extract basic information
        resource_name = contact_data.get('resourceName', '')
        etag = contact_data.get('etag', '')
        
        # Extract name information
        names = contact_data.get('names', [])
        display_name = given_name = family_name = middle_name = None
        if names:
            name = names[0]  # Use primary name
            display_name = name.get('displayName')
            given_name = name.get('givenName')
            family_name = name.get('familyName')
            middle_name = name.get('middleName')
        
        # Get modification time
        metadata = contact_data.get('metadata', {})
        modified_at = metadata.get('sources', [{}])[0].get('updateTime') if metadata.get('sources') else None
        
        cached_at = datetime.utcnow().isoformat()
        
        # Insert or update contact
        cursor.execute('''
            INSERT OR REPLACE INTO contacts 
            (resource_name, etag, display_name, given_name, family_name, middle_name, raw_data, cached_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (resource_name, etag, display_name, given_name, family_name, middle_name, 
              json.dumps(contact_data), cached_at, modified_at))
        
        # Clear existing email entries for this contact
        cursor.execute('DELETE FROM contact_emails WHERE resource_name = ?', (resource_name,))
        
        # Insert email addresses
        email_addresses = contact_data.get('emailAddresses', [])
        for email_data in email_addresses:
            email = email_data.get('value', '')
            email_type = email_data.get('type', '')
            is_primary = email_data.get('metadata', {}).get('primary', False)
            
            cursor.execute('''
                INSERT INTO contact_emails (resource_name, email, email_type, is_primary)
                VALUES (?, ?, ?, ?)
            ''', (resource_name, email, email_type, is_primary))
        
        conn.commit()
        logger.debug(f"Cached contact: {display_name} ({resource_name})")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error caching contact {contact_data.get('resourceName', 'unknown')}: {e}")
        raise
    finally:
        conn.close()


def cache_contacts(contacts_data: List[Dict[str, Any]]):
    """
    Cache multiple contacts in the database.
    
    Args:
        contacts_data: List of contact data from Google People API
    """
    for contact_data in contacts_data:
        cache_contact(contact_data)


def get_cached_contact_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a cached contact by email address.
    
    Args:
        email: The email address to search for
        
    Returns:
        Dict containing the contact data, or None if not found
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.raw_data 
            FROM contacts c
            JOIN contact_emails ce ON c.resource_name = ce.resource_name
            WHERE ce.email = ?
            ORDER BY ce.is_primary DESC
            LIMIT 1
        ''', (email,))
        
        row = cursor.fetchone()
        if row:
            return json.loads(row['raw_data'])
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving cached contact by email {email}: {e}")
        return None
    finally:
        conn.close()


def get_all_cached_contacts() -> List[Dict[str, Any]]:
    """
    Retrieve all cached contacts.
    
    Returns:
        List of contact data dictionaries
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT raw_data FROM contacts ORDER BY display_name')
        rows = cursor.fetchall()
        
        return [json.loads(row['raw_data']) for row in rows]
        
    except Exception as e:
        logger.error(f"Error retrieving all cached contacts: {e}")
        return []
    finally:
        conn.close()


def clear_contacts_cache():
    """
    Clear all cached contacts from the database.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM contact_emails')
        cursor.execute('DELETE FROM contacts')
        conn.commit()
        logger.info("Contacts cache cleared successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error clearing contacts cache: {e}")
        raise
    finally:
        conn.close()


def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the contacts cache.
    
    Returns:
        Dict containing cache statistics
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get total contacts count
        cursor.execute('SELECT COUNT(*) as total FROM contacts')
        total_contacts = cursor.fetchone()['total']
        
        # Get contacts with emails count
        cursor.execute('SELECT COUNT(DISTINCT resource_name) as with_emails FROM contact_emails')
        contacts_with_emails = cursor.fetchone()['with_emails']
        
        # Get last cache update
        cursor.execute('SELECT MAX(cached_at) as last_update FROM contacts')
        last_update = cursor.fetchone()['last_update']
        
        return {
            'total_contacts': total_contacts,
            'contacts_with_emails': contacts_with_emails,
            'last_update': last_update
        }
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}
    finally:
        conn.close()
