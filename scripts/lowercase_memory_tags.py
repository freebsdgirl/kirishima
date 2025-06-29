import sqlite3
import json
from pathlib import Path
from collections import defaultdict


memories_db_path = '../shared/db/brain/memories.db'

if not memories_db_path:
    raise ValueError("No memories DB path found in config.")

conn = sqlite3.connect(memories_db_path)
cursor = conn.cursor()

# Fetch all memory_id, tag pairs
cursor.execute("SELECT memory_id, tag FROM memory_tags")
rows = cursor.fetchall()

tags_by_memory = defaultdict(list)
for memory_id, tag in rows:
    tags_by_memory[memory_id].append(tag)

# For each memory_id, deduplicate tags by lowercased value
for memory_id, tags in tags_by_memory.items():
    lowercased = {}
    for tag in tags:
        lower_tag = tag.lower()
        if lower_tag not in lowercased:
            lowercased[lower_tag] = tag  # preserve first occurrence
    # Remove all tags for this memory_id
    cursor.execute("DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,))
    # Insert deduplicated, lowercased tags
    for lower_tag in lowercased:
        cursor.execute(
            "INSERT INTO memory_tags (memory_id, tag) VALUES (?, ?)",
            (memory_id, lower_tag)
        )

conn.commit()
conn.close()
print("All tags in memory_tags have been lowercased and deduplicated per memory.")
