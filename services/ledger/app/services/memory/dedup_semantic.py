"""
Service layer for semantic memory deduplication operations.

This module provides business logic for global memory deduplication using timeframe or keyword grouping.
"""

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3
import httpx
import json
import os
from typing import List, Dict
from datetime import datetime, timedelta

from shared.models.openai import OpenAICompletionRequest
from shared.models.ledger import MemoryDedupRequest, MemoryDedupResponse
from shared.prompt_loader import load_prompt
from app.util import _open_conn

from fastapi import HTTPException, status


def _get_all_memories():
    """Get all memories with their keywords and categories"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.id, m.memory, m.created_at,
               GROUP_CONCAT(DISTINCT mt.tag) as keywords,
               mc.category
        FROM memories m
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN memory_category mc ON m.id = mc.memory_id
        GROUP BY m.id, m.memory, m.created_at, mc.category
        ORDER BY m.created_at ASC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    memories = []
    for row in rows:
        mem_id, memory_text, created_at, keywords_str, category = row
        keywords = keywords_str.split(',') if keywords_str else []
        
        memories.append({
            'id': mem_id,
            'memory': memory_text,
            'created_at': created_at,
            'keywords': keywords,
            'category': category
        })
    
    return memories


def _group_memories_by_timeframe(memories: List[Dict], days: int) -> List[List[str]]:
    """Group memories by timeframe windows"""
    groups = []
    current_group = []
    current_start = None
    
    for memory in memories:
        if not memory['created_at']:
            continue
            
        try:
            created_at = datetime.fromisoformat(memory['created_at'].replace('Z', '+00:00'))
            
            if current_start is None:
                current_start = created_at
                current_group = [memory['id']]
            else:
                time_diff = (created_at - current_start).days
                if time_diff <= days:
                    current_group.append(memory['id'])
                else:
                    if len(current_group) >= 2:
                        groups.append(current_group)
                    current_start = created_at
                    current_group = [memory['id']]
        except Exception as e:
            logger.error(f"Error parsing date for memory {memory['id']}: {e}")
            continue
    
    # Add final group
    if len(current_group) >= 2:
        groups.append(current_group)
    
    return groups


def _group_memories_by_keyword_overlap(memories: List[Dict], min_shared: int) -> List[List[str]]:
    """Group memories by keyword overlap"""
    groups = []
    processed = set()
    
    for i, mem1 in enumerate(memories):
        if mem1['id'] in processed or not mem1['keywords']:
            continue
            
        current_group = [mem1['id']]
        processed.add(mem1['id'])
        
        for j, mem2 in enumerate(memories[i+1:], i+1):
            if mem2['id'] in processed or not mem2['keywords']:
                continue
                
            # Count shared keywords
            shared = set(mem1['keywords']) & set(mem2['keywords'])
            if len(shared) >= min_shared:
                current_group.append(mem2['id'])
                processed.add(mem2['id'])
        
        if len(current_group) >= 2:
            groups.append(current_group)
    
    return groups


async def _process_memory_groups_semantic(memory_groups: List[List[str]], grouping_type: str) -> List[Dict]:
    """Process memory groups for deduplication using LLM"""
    results = []
    
    if not memory_groups:
        return results

    api_port = os.getenv("API_PORT", 4200)
    
    async with httpx.AsyncClient(timeout=180) as client:
        for i, group in enumerate(memory_groups):
            if len(group) < 2:
                continue
                
            # Get memory details for this group
            conn = _open_conn()
            cursor = conn.cursor()
            
            memory_data = []
            for mem_id in group:
                cursor.execute("""
                    SELECT m.id, m.memory,
                           GROUP_CONCAT(DISTINCT mt.tag) as keywords,
                           mc.category
                    FROM memories m
                    LEFT JOIN memory_tags mt ON m.id = mt.memory_id
                    LEFT JOIN memory_category mc ON m.id = mc.memory_id
                    WHERE m.id = ?
                    GROUP BY m.id, m.memory, mc.category
                """, (mem_id,))
                
                row = cursor.fetchone()
                if row:
                    mem_id, memory_text, keywords_str, category = row
                    keywords = keywords_str.split(',') if keywords_str else []
                    memory_data.append({
                        'id': mem_id,
                        'memory': memory_text,
                        'keywords': keywords,
                        'category': category
                    })
            
            conn.close()
            
            if not memory_data:
                continue
            
            # Format memories for LLM
            memory_lines = []
            for mem in memory_data:
                keywords_str = ",".join(mem['keywords']) if mem['keywords'] else ""
                memory_lines.append(f"{mem['id']}|{mem['memory']}|{keywords_str}|{mem['category'] or ''}")
            
            memory_block = "\n".join(memory_lines)
            
            # Get deduplication suggestions from LLM
            prompt = load_prompt("ledger", "memory", "dedup_memories", memory_block=memory_block)
            
            request = OpenAICompletionRequest(
                model="gpt-4.1",
                prompt=prompt
            )
            
            try:
                response = await client.post(f"http://api:{api_port}/v1/completions", json=request.model_dump())
                response.raise_for_status()
                data = response.json()
                
                completion_text = data['choices'][0]['content'].strip()
                suggestions = json.loads(completion_text)
                
                # Process suggestions
                updated_memories = {}
                deleted_memories = []
                
                if 'update' in suggestions:
                    for mem_id, update_data in suggestions['update'].items():
                        try:
                            # Apply memory updates
                            conn = _open_conn()
                            cursor = conn.cursor()
                            
                            if 'memory' in update_data:
                                cursor.execute("UPDATE memories SET memory = ? WHERE id = ?", 
                                             (update_data['memory'], mem_id))
                            
                            # Update keywords
                            if 'keywords' in update_data:
                                cursor.execute("DELETE FROM memory_tags WHERE memory_id = ?", (mem_id,))
                                for keyword in update_data['keywords']:
                                    cursor.execute("INSERT INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                                                 (mem_id, keyword.lower()))
                            
                            # Update category
                            if 'category' in update_data:
                                cursor.execute("DELETE FROM memory_category WHERE memory_id = ?", (mem_id,))
                                if update_data['category']:
                                    cursor.execute("INSERT INTO memory_category (memory_id, category) VALUES (?, ?)",
                                                 (mem_id, update_data['category']))
                            
                            conn.commit()
                            conn.close()
                            updated_memories[mem_id] = update_data
                            
                        except Exception as e:
                            logger.error(f"Error updating memory {mem_id}: {e}")
                            if 'conn' in locals():
                                conn.close()
                            continue
                
                if 'delete' in suggestions:
                    for mem_id in suggestions['delete']:
                        try:
                            conn = _open_conn()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM memory_tags WHERE memory_id = ?", (mem_id,))
                            cursor.execute("DELETE FROM memory_category WHERE memory_id = ?", (mem_id,))
                            cursor.execute("DELETE FROM memory_topics WHERE memory_id = ?", (mem_id,))
                            cursor.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
                            conn.commit()
                            conn.close()
                            deleted_memories.append(mem_id)
                            
                        except Exception as e:
                            logger.error(f"Error deleting memory {mem_id}: {e}")
                            if 'conn' in locals():
                                conn.close()
                            continue
                
                results.append({
                    "status": "completed",
                    "grouping_strategy": grouping_type,
                    "group": f"{grouping_type.title()} group {i+1}",
                    "updated_memories": updated_memories,
                    "deleted_memories": deleted_memories
                })
                
            except Exception as e:
                logger.error(f"Error processing group {i+1}: {e}")
                continue
    
    return results


async def _memory_deduplicate_semantic(grouping: str, timeframe_days: int = 7, min_shared_keywords: int = 2, dry_run: bool = False) -> MemoryDedupResponse:
    """
    Semantic memory deduplication service function.
    
    Args:
        grouping: Grouping strategy ("timeframe" or "keyword")
        timeframe_days: Days for timeframe grouping
        min_shared_keywords: Minimum shared keywords for keyword grouping
        dry_run: If True, only analyze without making changes
        
    Returns:
        MemoryDedupResponse with results or dry run information
    """
    ALLOWED_GROUPINGS = ["timeframe", "keyword"]
    
    if grouping not in ALLOWED_GROUPINGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid grouping strategy. Must be one of: {ALLOWED_GROUPINGS}"
        )
    
    # Get all memories
    memories = _get_all_memories()
    
    if not memories:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No memories found."
        )
    
    # Group memories based on strategy
    if grouping == "timeframe":
        memory_groups = _group_memories_by_timeframe(memories, timeframe_days)
    else:  # keyword
        memory_groups = _group_memories_by_keyword_overlap(memories, min_shared_keywords)
    
    if dry_run:
        return MemoryDedupResponse(
            status="dry_run",
            grouping_strategy=grouping,
            message=f"Would analyze {len(memories)} memories using {grouping} strategy",
            dry_run_info={
                "total_memories": len(memories),
                "groups_found": len(memory_groups),
                "estimated_api_calls": len(memory_groups),
                "parameters": {
                    "timeframe_days": timeframe_days if grouping == "timeframe" else None,
                    "min_shared_keywords": min_shared_keywords if grouping == "keyword" else None
                }
            }
        )
    
    if not memory_groups:
        return MemoryDedupResponse(
            status="no_groups_found",
            grouping_strategy=grouping,
            message="No memory groups found for deduplication."
        )
    
    # Process groups
    results = await _process_memory_groups_semantic(memory_groups, grouping)
    
    if not results:
        return MemoryDedupResponse(
            status="no_results",
            grouping_strategy=grouping,
            message="No memory groups processed for deduplication."
        )
    
    logger.info(f"Semantic deduplication completed for {len(results)} groups using {grouping} strategy.")
    
    return MemoryDedupResponse(
        status="completed",
        grouping_strategy=grouping,
        message=f"Semantic deduplication completed for {len(results)} groups",
        results=results
    )
