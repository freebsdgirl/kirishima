#!/usr/bin/env python3
"""Check the current state of the ledger database."""

import sqlite3
import sys
import os

def check_database_state():
    """Check the current state of the ledger database."""
    # Try both Docker and local paths
    db_paths = [
        "/home/randi/.kirishima/ledger.db",
        "/app/data/ledger.db"
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print(f"Database not found at any of: {db_paths}")
        return
    
    print(f"Using database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Check memories
        cursor = conn.execute("SELECT COUNT(*) FROM memories")
        memory_count = cursor.fetchone()[0]
        print(f"Total memories: {memory_count}")
        
        # Check messages
        cursor = conn.execute("SELECT COUNT(*) FROM user_messages")
        message_count = cursor.fetchone()[0]
        print(f"Total messages: {message_count}")
        
        # Check topics
        cursor = conn.execute("SELECT COUNT(*) FROM topics")
        topic_count = cursor.fetchone()[0]
        print(f"Total topics: {topic_count}")
        
        # Check memory tags
        cursor = conn.execute("SELECT COUNT(*) FROM memory_tags")
        tag_count = cursor.fetchone()[0]
        print(f"Total memory tags: {tag_count}")
        
        # Check summaries
        cursor = conn.execute("SELECT COUNT(*) FROM summaries")
        summary_count = cursor.fetchone()[0]
        print(f"Total summaries: {summary_count}")
        
        # Sample some memories
        print("\nSample memories:")
        cursor = conn.execute("SELECT id, content, created FROM memories ORDER BY created DESC LIMIT 5")
        for row in cursor.fetchall():
            print(f"  ID: {row[0]}, Created: {row[2]}")
            print(f"    Content: {row[1][:100]}...")
        
        # Check memory categories
        cursor = conn.execute("SELECT category, COUNT(*) FROM memory_category GROUP BY category")
        print("\nMemory categories:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} memories")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_database_state()
