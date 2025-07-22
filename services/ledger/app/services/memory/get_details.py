from shared.models.ledger import MemoryEntry

from app.util import _open_conn

from typing import List, Set

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")


def _get_memory_details(memory_ids: Set[str]) -> List[MemoryEntry]:
    """
    Retrieve complete memory details for a set of memory IDs.
    
    Args:
        memory_ids (Set[str]): Set of memory IDs to retrieve details for.
    
    Returns:
        List[MemoryEntry]: A list of complete memory entries.
    """
    if not memory_ids:
        return []
    
    with _open_conn() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in memory_ids)
        
        # Get basic memory data
        cursor.execute(f"""
            SELECT id, memory, created_at, access_count, last_accessed
            FROM memories 
            WHERE id IN ({placeholders})
            ORDER BY created_at DESC
        """, list(memory_ids))
        
        memories = cursor.fetchall()
        
        # Get keywords for all memories
        cursor.execute(f"""
            SELECT memory_id, tag 
            FROM memory_tags 
            WHERE memory_id IN ({placeholders})
        """, list(memory_ids))
        
        keyword_map = {}
        for memory_id, tag in cursor.fetchall():
            keyword_map.setdefault(memory_id, []).append(tag)
        
        # Get categories for all memories
        cursor.execute(f"""
            SELECT memory_id, category 
            FROM memory_category 
            WHERE memory_id IN ({placeholders})
        """, list(memory_ids))
        
        category_map = {}
        for memory_id, category in cursor.fetchall():
            category_map[memory_id] = category
        
        # Get topic associations for all memories
        cursor.execute(f"""
            SELECT memory_id, topic_id 
            FROM memory_topics 
            WHERE memory_id IN ({placeholders})
        """, list(memory_ids))
        
        topic_map = {}
        for memory_id, topic_id in cursor.fetchall():
            topic_map[memory_id] = topic_id
        
        # Get topic names for efficient lookup
        if topic_map:
            topic_ids = list(set(topic_map.values()))
            topic_placeholders = ','.join('?' for _ in topic_ids)
            cursor.execute(f"""
                SELECT id, name 
                FROM topics 
                WHERE id IN ({topic_placeholders})
            """, topic_ids)
            
            topic_name_map = {}
            for topic_id, topic_name in cursor.fetchall():
                topic_name_map[topic_id] = topic_name
        else:
            topic_name_map = {}
        
        # Build complete memory entries
        result = []
        for row in memories:
            memory_id = row[0]
            topic_id = topic_map.get(memory_id)
            topic_name = topic_name_map.get(topic_id) if topic_id else None
            
            result.append(MemoryEntry(
                id=memory_id,
                memory=row[1],
                created_at=row[2],
                access_count=row[3] or 0,
                last_accessed=row[4],
                keywords=keyword_map.get(memory_id, []),
                category=category_map.get(memory_id),
                topic_id=topic_id,
                topic_name=topic_name
            ))
        
        return result