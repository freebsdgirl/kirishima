from fastapi import APIRouter, HTTPException, status, Query
import sqlite3
import json
from typing import List, Dict

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

router = APIRouter()

@router.get("/memories/dedup/keywords", response_model=Dict[str, List[List[str]]])
def deduplicate_memories_keyword(
    min_shared_keywords: int = Query(2, description="Minimum number of shared keywords to consider memories as duplicates.")
):
    """
    Find groups of memories that share more than N keywords in common.
    Args:
        min_shared_keywords (int): Minimum number of shared keywords to consider as a group.
    Returns:
        dict: {"groups": [[memory_id1, memory_id2, ...], ...]} where each group shares >N keywords.
    """
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            # Fetch all memory ids and their tags
            cursor.execute("SELECT memory_id, tag FROM memory_tags")
            tag_rows = cursor.fetchall()
            # Build memory_id -> set of tags
            from collections import defaultdict
            mem_tags = defaultdict(set)
            for mem_id, tag in tag_rows:
                mem_tags[mem_id].add(tag.lower())
            # Find groups with >N keywords in common
            groups = []
            checked = set()
            mem_ids = list(mem_tags.keys())
            for i, mem1 in enumerate(mem_ids):
                for j in range(i+1, len(mem_ids)):
                    mem2 = mem_ids[j]
                    if (mem1, mem2) in checked or (mem2, mem1) in checked:
                        continue
                    shared = mem_tags[mem1] & mem_tags[mem2]
                    if len(shared) > min_shared_keywords:
                        # See if this group overlaps with an existing group
                        found = False
                        for group in groups:
                            if mem1 in group or mem2 in group:
                                group.update([mem1, mem2])
                                found = True
                                break
                        if not found:
                            groups.append(set([mem1, mem2]))
                    checked.add((mem1, mem2))
            # Convert sets to sorted lists for output, and sort by number of shared keywords (descending)
            # We'll use the first two memories in each group to compute the shared keyword count
            def shared_count(group):
                if len(group) < 2:
                    return 0
                # Compute max shared keywords between any two in the group
                group_list = list(group)
                max_shared = 0
                for i in range(len(group_list)):
                    for j in range(i+1, len(group_list)):
                        shared = mem_tags[group_list[i]] & mem_tags[group_list[j]]
                        if len(shared) > max_shared:
                            max_shared = len(shared)
                return max_shared
            result = [sorted(list(g)) for g in groups if len(g) > 1]
            result.sort(key=shared_count, reverse=True)
        return {"groups": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding duplicate memories: {str(e)}")