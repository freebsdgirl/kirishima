"""
Global memory deduplication using timeframe or keyword grouping.
Simple approach with dry run support as requested.
"""

from fastapi import APIRouter, HTTPException, status, Query
from shared.log_config import get_logger
from shared.models.openai import OpenAICompletionRequest
from shared.prompt_loader import load_prompt
import sqlite3
import httpx
import json
import os
from typing import List, Dict
from datetime import datetime, timedelta

logger = get_logger(f"ledger.{__name__}")
router = APIRouter()

ALLOWED_GROUPINGS = ["timeframe", "keyword"]

def _open_conn():
    import json
    with open('/app/config/config.json') as f:
        config = json.load(f)
        db_path = config["db"]["ledger"]
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

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
        keywords = [k.strip() for k in keywords_str.split(",") if k] if keywords_str else []
        
        memories.append({
            "id": mem_id,
            "memory": memory_text,
            "created_at": created_at,
            "category": category,
            "keywords": keywords
        })
    
    return memories

def _group_memories_by_timeframe(memories: List[Dict], days: int = 7) -> List[List[Dict]]:
    """Group memories by creation timeframe"""
    if not memories:
        return []
    
    # Sort by creation date
    memories = sorted(memories, key=lambda m: m["created_at"])
    
    groups = []
    current_group = []
    group_start = None
    
    for memory in memories:
        try:
            created_date = datetime.fromisoformat(memory["created_at"].replace("Z", "+00:00"))
            
            if not current_group:
                current_group = [memory]
                group_start = created_date
            elif (created_date - group_start).days <= days:
                current_group.append(memory)
            else:
                # Close current group and start new one
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = [memory]
                group_start = created_date
        except Exception as e:
            logger.error(f"Error parsing date for memory {memory['id']}: {e}")
            continue
    
    # Add final group
    if len(current_group) > 1:
        groups.append(current_group)
    
    return groups

def _group_memories_by_keyword(memories: List[Dict], min_matches: int = 2) -> List[List[Dict]]:
    """Group memories by shared keywords"""
    groups = []
    used_memory_ids = set()
    
    for i, mem1 in enumerate(memories):
        if mem1["id"] in used_memory_ids:
            continue
            
        current_group = [mem1]
        used_memory_ids.add(mem1["id"])
        keywords1 = set(mem1["keywords"])
        
        for j, mem2 in enumerate(memories[i+1:], i+1):
            if mem2["id"] in used_memory_ids:
                continue
                
            keywords2 = set(mem2["keywords"])
            shared_keywords = keywords1.intersection(keywords2)
            
            if len(shared_keywords) >= min_matches:
                current_group.append(mem2)
                used_memory_ids.add(mem2["id"])
        
        # Only include groups with multiple memories
        if len(current_group) > 1:
            groups.append(current_group)
    
    return groups

async def _process_memory_group_with_llm(group: List[Dict]) -> Dict:
    """Process a group of memories with LLM to get deduplication recommendations"""
    # Prepare memory block for LLM
    memory_lines = []
    for mem in group:
        keywords_str = ",".join(mem["keywords"]) if mem["keywords"] else ""
        memory_lines.append(f"{mem['id']}|{mem['memory']}|{keywords_str}|{mem['category'] or ''}")
    
    memory_block = "\n".join(memory_lines)
    
    # Load the dedup prompt
    prompt = load_prompt("ledger", "memory", "dedup_memories", memory_block=memory_block)
    
    # Create OpenAI request
    request = OpenAICompletionRequest(
        model="gpt-4.1",
        prompt=prompt,
        temperature=0.7,
        max_tokens=2000,
        provider="openai"
    )
    
    # Call the API
    api_port = os.getenv("API_PORT", "4200")
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"http://api:{api_port}/v1/completions",
                json=request.model_dump()
            )
            response.raise_for_status()
            result = response.json()
            
            # Parse LLM response
            llm_content = result['choices'][0]['content'].strip()
            return json.loads(llm_content)
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get LLM response: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to get LLM response: {e}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Raw content: {llm_content[:500]}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to parse LLM response: {e}"
            )

async def _apply_dedup_operations(operations: Dict) -> Dict:
    """Apply the deduplication operations (updates and deletes)"""
    from app.memory.patch import _memory_patch
    from app.memory.delete import _memory_delete
    from shared.models.ledger import MemoryEntry
    
    updated_count = 0
    deleted_count = 0
    errors = []
    
    try:
        # Apply updates
        for memory_id, update_data in operations.get("update", {}).items():
            try:
                memory_entry = MemoryEntry(
                    id=memory_id,
                    memory=update_data.get("memory"),
                    keywords=update_data.get("keywords"),
                    category=update_data.get("category")
                )
                _memory_patch(memory_entry)
                updated_count += 1
                logger.info(f"Updated memory {memory_id}")
            except Exception as e:
                error_msg = f"Failed to update {memory_id}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Apply deletions
        for memory_id in operations.get("delete", []):
            try:
                _memory_delete(memory_id)
                deleted_count += 1
                logger.info(f"Deleted memory {memory_id}")
            except Exception as e:
                error_msg = f"Failed to delete {memory_id}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
                
    except Exception as e:
        error_msg = f"Unexpected error applying operations: {e}"
        errors.append(error_msg)
        logger.error(error_msg)
    
    return {
        "updated": updated_count,
        "deleted": deleted_count,
        "errors": errors
    }

@router.get("/memories/_dedup_semantic")
async def dedup_semantic(
    dry_run: bool = Query(True, description="If true, only show what would be deduplicated."),
    grouping_strategy: str = Query("timeframe", description="Grouping: 'timeframe' or 'keyword'"),
    min_keyword_matches: int = Query(2, description="Minimum keyword matches for keyword grouping."),
    timeframe_days: int = Query(7, description="Days for timeframe grouping.")
):
    """
    Deduplicate memories globally, grouped by timeframe or keyword overlap. Always supports dry_run.
    """
    if grouping_strategy not in ALLOWED_GROUPINGS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid grouping_strategy. Must be one of {ALLOWED_GROUPINGS}"
        )
    
    memories = _get_all_memories()
    
    if grouping_strategy == "timeframe":
        groups = _group_memories_by_timeframe(memories, days=timeframe_days)
    else:  # keyword
        groups = _group_memories_by_keyword(memories, min_matches=min_keyword_matches)
    
    if dry_run:
        return {
            "strategy": grouping_strategy,
            "groups": [[m["id"] for m in group] for group in groups],
            "group_count": len(groups),
            "memory_count": len(memories)
        }
    
    # Process each group with LLM and apply deduplication
    total_operations = {"update": {}, "delete": []}
    group_results = []
    
    for i, group in enumerate(groups):
        try:
            logger.info(f"Processing group {i+1}/{len(groups)} with {len(group)} memories")
            operations = await _process_memory_group_with_llm(group)
            
            # Merge operations
            if "update" in operations:
                total_operations["update"].update(operations["update"])
            if "delete" in operations:
                total_operations["delete"].extend(operations["delete"])
                
            group_results.append({
                "group_index": i,
                "memory_ids": [m["id"] for m in group],
                "operations": operations
            })
            
        except Exception as e:
            error_msg = f"Failed to process group {i}: {e}"
            logger.error(error_msg)
            group_results.append({
                "group_index": i,
                "memory_ids": [m["id"] for m in group],
                "error": error_msg
            })
    
    # Apply all operations
    if total_operations["update"] or total_operations["delete"]:
        application_results = await _apply_dedup_operations(total_operations)
    else:
        application_results = {"updated": 0, "deleted": 0, "errors": []}
    
    return {
        "strategy": grouping_strategy,
        "groups_processed": len(groups),
        "memory_count": len(memories),
        "operations": total_operations,
        "results": application_results,
        "group_details": group_results
    }
