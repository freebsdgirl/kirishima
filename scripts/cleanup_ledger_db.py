#!/usr/bin/env python3
"""
Database cleanup script for the Kirishima ledger service.

This script validates referential integrity and removes orphaned records that violate
foreign key constraints. It should be run after enabling foreign key enforcement
to clean up any existing inconsistent data.

Operations performed:
1. Remove orphaned topics (topics not referenced by any user_messages)
2. Remove orphaned memory_topics (referencing non-existent memories or topics)
3. Remove orphaned memory_category (referencing non-existent memories)
4. Remove orphaned memory_tags (referencing non-existent memories)

Usage:
    python cleanup_ledger_db.py [--dry-run] [--config-path /path/to/config.json]
"""

import sqlite3
import json
import argparse
import sys
from typing import List, Tuple
from pathlib import Path

def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in config file {config_path}")
        sys.exit(1)

def get_db_connection(config: dict) -> sqlite3.Connection:
    """Get database connection from config."""
    try:
        db_path = 'buffer.db'
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        # Don't enable FK constraints yet - we need to clean up first
        return conn
    except KeyError:
        print("Error: 'db.ledger' not found in config")
        sys.exit(1)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def find_orphaned_topics(conn: sqlite3.Connection) -> List[str]:
    """Find topics that are not referenced by any user_messages."""
    cursor = conn.cursor()
    
    # Find topics that don't have any user_messages referencing them
    cursor.execute("""
        SELECT t.id, t.name 
        FROM topics t 
        LEFT JOIN user_messages um ON t.id = um.topic_id 
        WHERE um.topic_id IS NULL
    """)
    
    orphans = cursor.fetchall()
    return [(topic_id, name) for topic_id, name in orphans]

def find_orphaned_memory_topics(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    """Find memory_topics entries with non-existent memory_id or topic_id."""
    cursor = conn.cursor()
    
    # Find memory_topics with non-existent memory_id
    cursor.execute("""
        SELECT mt.memory_id, mt.topic_id 
        FROM memory_topics mt 
        LEFT JOIN memories m ON mt.memory_id = m.id 
        WHERE m.id IS NULL
    """)
    invalid_memory = cursor.fetchall()
    
    # Find memory_topics with non-existent topic_id
    cursor.execute("""
        SELECT mt.memory_id, mt.topic_id 
        FROM memory_topics mt 
        LEFT JOIN topics t ON mt.topic_id = t.id 
        WHERE t.id IS NULL
    """)
    invalid_topic = cursor.fetchall()
    
    # Combine and deduplicate
    all_invalid = set(invalid_memory + invalid_topic)
    return list(all_invalid)

def find_orphaned_memory_category(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    """Find memory_category entries with non-existent memory_id."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT mc.memory_id, mc.category 
        FROM memory_category mc 
        LEFT JOIN memories m ON mc.memory_id = m.id 
        WHERE m.id IS NULL
    """)
    
    return cursor.fetchall()

def find_orphaned_memory_tags(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    """Find memory_tags entries with non-existent memory_id."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT mt.memory_id, mt.tag 
        FROM memory_tags mt 
        LEFT JOIN memories m ON mt.memory_id = m.id 
        WHERE m.id IS NULL
    """)
    
    return cursor.fetchall()

def clean_orphaned_topics(conn: sqlite3.Connection, orphans: List[Tuple[str, str]], dry_run: bool) -> int:
    """Remove orphaned topics."""
    if not orphans:
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for topic_id, name in orphans:
        if dry_run:
            print(f"  Would delete topic: {topic_id} ('{name}')")
        else:
            cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            print(f"  Deleted topic: {topic_id} ('{name}')")
        count += 1
    
    if not dry_run:
        conn.commit()
    
    return count

def clean_orphaned_memory_topics(conn: sqlite3.Connection, orphans: List[Tuple[str, str]], dry_run: bool) -> int:
    """Remove orphaned memory_topics entries."""
    if not orphans:
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for memory_id, topic_id in orphans:
        if dry_run:
            print(f"  Would delete memory_topics: memory_id={memory_id}, topic_id={topic_id}")
        else:
            cursor.execute("DELETE FROM memory_topics WHERE memory_id = ? AND topic_id = ?", 
                         (memory_id, topic_id))
            print(f"  Deleted memory_topics: memory_id={memory_id}, topic_id={topic_id}")
        count += 1
    
    if not dry_run:
        conn.commit()
    
    return count

def clean_orphaned_memory_category(conn: sqlite3.Connection, orphans: List[Tuple[str, str]], dry_run: bool) -> int:
    """Remove orphaned memory_category entries."""
    if not orphans:
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for memory_id, category in orphans:
        if dry_run:
            print(f"  Would delete memory_category: memory_id={memory_id}, category='{category}'")
        else:
            cursor.execute("DELETE FROM memory_category WHERE memory_id = ? AND category = ?", 
                         (memory_id, category))
            print(f"  Deleted memory_category: memory_id={memory_id}, category='{category}'")
        count += 1
    
    if not dry_run:
        conn.commit()
    
    return count

def clean_orphaned_memory_tags(conn: sqlite3.Connection, orphans: List[Tuple[str, str]], dry_run: bool) -> int:
    """Remove orphaned memory_tags entries."""
    if not orphans:
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for memory_id, tag in orphans:
        if dry_run:
            print(f"  Would delete memory_tags: memory_id={memory_id}, tag='{tag}'")
        else:
            cursor.execute("DELETE FROM memory_tags WHERE memory_id = ? AND tag = ?", 
                         (memory_id, tag))
            print(f"  Deleted memory_tags: memory_id={memory_id}, tag='{tag}'")
        count += 1
    
    if not dry_run:
        conn.commit()
    
    return count

def get_table_counts(conn: sqlite3.Connection) -> dict:
    """Get current record counts for all tables."""
    cursor = conn.cursor()
    tables = ['topics', 'memory_topics', 'memory_category', 'memory_tags', 'memories', 'user_messages']
    counts = {}
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cursor.fetchone()[0]
    
    return counts

def main():
    parser = argparse.ArgumentParser(description="Clean up orphaned records in ledger database")
    parser.add_argument("--dry-run", action="store_true", 
                      help="Show what would be deleted without actually deleting")
    parser.add_argument("--config-path", default="/home/randi/.kirishima/config.json",
                      help="Path to config.json file")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config_path)
    
    # Connect to database
    conn = get_db_connection(config)
    
    print("=== Kirishima Ledger Database Cleanup ===")
    print(f"Database: {config['db']['ledger']}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE CLEANUP'}")
    print()
    
    # Show initial table counts
    initial_counts = get_table_counts(conn)
    print("Initial table counts:")
    for table, count in initial_counts.items():
        print(f"  {table}: {count}")
    print()
    
    total_deleted = 0
    
    try:
        # 1. Find and clean orphaned topics
        print("1. Checking for orphaned topics...")
        orphaned_topics = find_orphaned_topics(conn)
        if orphaned_topics:
            print(f"   Found {len(orphaned_topics)} orphaned topics")
            deleted = clean_orphaned_topics(conn, orphaned_topics, args.dry_run)
            total_deleted += deleted
        else:
            print("   No orphaned topics found")
        print()
        
        # 2. Find and clean orphaned memory_topics
        print("2. Checking for orphaned memory_topics...")
        orphaned_memory_topics = find_orphaned_memory_topics(conn)
        if orphaned_memory_topics:
            print(f"   Found {len(orphaned_memory_topics)} orphaned memory_topics entries")
            deleted = clean_orphaned_memory_topics(conn, orphaned_memory_topics, args.dry_run)
            total_deleted += deleted
        else:
            print("   No orphaned memory_topics found")
        print()
        
        # 3. Find and clean orphaned memory_category
        print("3. Checking for orphaned memory_category...")
        orphaned_memory_category = find_orphaned_memory_category(conn)
        if orphaned_memory_category:
            print(f"   Found {len(orphaned_memory_category)} orphaned memory_category entries")
            deleted = clean_orphaned_memory_category(conn, orphaned_memory_category, args.dry_run)
            total_deleted += deleted
        else:
            print("   No orphaned memory_category found")
        print()
        
        # 4. Find and clean orphaned memory_tags
        print("4. Checking for orphaned memory_tags...")
        orphaned_memory_tags = find_orphaned_memory_tags(conn)
        if orphaned_memory_tags:
            print(f"   Found {len(orphaned_memory_tags)} orphaned memory_tags entries")
            deleted = clean_orphaned_memory_tags(conn, orphaned_memory_tags, args.dry_run)
            total_deleted += deleted
        else:
            print("   No orphaned memory_tags found")
        print()
        
        # Show final results
        if not args.dry_run:
            final_counts = get_table_counts(conn)
            print("Final table counts:")
            for table, count in final_counts.items():
                initial = initial_counts[table]
                diff = initial - count
                status = f"(-{diff})" if diff > 0 else ""
                print(f"  {table}: {count} {status}")
            print()
        
        print(f"Total records {'would be deleted' if args.dry_run else 'deleted'}: {total_deleted}")
        
        if args.dry_run:
            print("\nRun without --dry-run to perform the actual cleanup.")
        else:
            print("\nCleanup completed successfully!")
            print("Foreign key constraints should now be fully enforceable.")
    
    except Exception as e:
        print(f"Error during cleanup: {e}")
        if not args.dry_run:
            conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()
