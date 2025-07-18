#!/usr/bin/env python3
"""
Consolidate duplicate topic names in the ledger database.

This script:
1. Finds all duplicate topic names (same name, different IDs)
2. For each set of duplicates, keeps the earliest created topic ID
3. Updates all references (user_messages.topic_id, memory_topics.topic_id) to use the canonical ID
4. Deletes the duplicate topic records

The script preserves all data relationships while eliminating topic fragmentation.
"""

import sqlite3
import json
from collections import defaultdict

def load_config():
    """Load the ledger database path from config."""
    return 'buffer.db'

def find_duplicate_topics(conn):
    """
    Find all topic names that have multiple IDs.
    Returns a dict: {topic_name: [list of (id, created_at) tuples]}
    """
    cursor = conn.execute("""
        SELECT id, name, created_at
        FROM topics 
        WHERE name IS NOT NULL AND name != ''
        ORDER BY name, created_at
    """)
    
    topic_groups = defaultdict(list)
    for row in cursor:
        topic_id, name, created_at = row
        topic_groups[name].append((topic_id, created_at))
    
    # Only return groups with duplicates
    duplicates = {name: ids for name, ids in topic_groups.items() if len(ids) > 1}
    return duplicates

def consolidate_topic_duplicates(conn, duplicates):
    """
    For each duplicate topic name, consolidate all references to use the earliest ID.
    """
    total_consolidated = 0
    total_deleted = 0
    
    for topic_name, id_list in duplicates.items():
        # Sort by created_at to get the earliest (canonical) ID
        id_list.sort(key=lambda x: x[1])  # Sort by created_at
        canonical_id = id_list[0][0]
        duplicate_ids = [id_tuple[0] for id_tuple in id_list[1:]]
        
        print(f"\nConsolidating topic '{topic_name}':")
        print(f"  Canonical ID: {canonical_id} (created: {id_list[0][1]})")
        print(f"  Duplicate IDs to merge: {duplicate_ids}")
        
        # Update user_messages to point to canonical topic ID
        for dup_id in duplicate_ids:
            cursor = conn.execute("""
                UPDATE user_messages 
                SET topic_id = ? 
                WHERE topic_id = ?
            """, (canonical_id, dup_id))
            affected_messages = cursor.rowcount
            print(f"    Updated {affected_messages} user_messages from {dup_id} to {canonical_id}")
        
        # Update memory_topics to point to canonical topic ID
        # Note: We need to handle potential primary key conflicts
        for dup_id in duplicate_ids:
            # First, find memory_topics that would conflict (same memory_id, canonical topic_id already exists)
            cursor = conn.execute("""
                SELECT memory_id FROM memory_topics 
                WHERE topic_id = ? 
                AND memory_id IN (
                    SELECT memory_id FROM memory_topics WHERE topic_id = ?
                )
            """, (dup_id, canonical_id))
            conflicting_memories = [row[0] for row in cursor.fetchall()]
            
            if conflicting_memories:
                print(f"    Found {len(conflicting_memories)} memory_topics that would conflict - deleting duplicates")
                # Delete the conflicting entries (keep the canonical ones)
                for memory_id in conflicting_memories:
                    conn.execute("""
                        DELETE FROM memory_topics 
                        WHERE memory_id = ? AND topic_id = ?
                    """, (memory_id, dup_id))
            
            # Now update the remaining ones
            cursor = conn.execute("""
                UPDATE memory_topics 
                SET topic_id = ? 
                WHERE topic_id = ?
            """, (canonical_id, dup_id))
            affected_memory_topics = cursor.rowcount
            print(f"    Updated {affected_memory_topics} memory_topics from {dup_id} to {canonical_id}")
        
        # Delete the duplicate topic records
        for dup_id in duplicate_ids:
            conn.execute("DELETE FROM topics WHERE id = ?", (dup_id,))
            total_deleted += 1
            print(f"    Deleted duplicate topic record: {dup_id}")
        
        total_consolidated += len(duplicate_ids)
    
    return total_consolidated, total_deleted

def main():
    """Main consolidation function."""
    db_path = load_config()
    print(f"Connecting to database: {db_path}")
    
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA foreign_keys=ON;")
    
    try:
        # Find duplicates
        duplicates = find_duplicate_topics(conn)
        
        if not duplicates:
            print("No duplicate topic names found.")
            return
        
        print(f"Found {len(duplicates)} topic names with duplicates:")
        for name, ids in duplicates.items():
            print(f"  '{name}': {len(ids)} IDs")
        
        # Ask for confirmation
        response = input(f"\nProceed with consolidation? (y/N): ").strip().lower()
        if response != 'y':
            print("Consolidation cancelled.")
            return
        
        # Perform consolidation
        total_consolidated, total_deleted = consolidate_topic_duplicates(conn, duplicates)
        
        # Commit changes
        conn.commit()
        print(f"\nConsolidation complete!")
        print(f"  Consolidated {total_consolidated} duplicate topic IDs")
        print(f"  Deleted {total_deleted} duplicate topic records")
        
        # Verify results
        print("\nVerifying results...")
        remaining_duplicates = find_duplicate_topics(conn)
        if remaining_duplicates:
            print(f"WARNING: {len(remaining_duplicates)} duplicate groups still exist!")
            for name, ids in remaining_duplicates.items():
                print(f"  '{name}': {len(ids)} IDs")
        else:
            print("All duplicates successfully consolidated.")
    
    except Exception as e:
        print(f"Error during consolidation: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
