"""
Service layer for memory deduplication operations.

This module contains the business logic extracted from the original dedup endpoint.
The logic is preserved exactly as it was in the original implementation.
"""

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import os
import httpx
from app.util import _open_conn
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple

from app.topic.get_all_topics import _get_all_topics
from app.services.memory.get_memory_by_topic import _get_memory_by_topic
from app.services.memory.get import _get_memory
from app.services.memory.delete import _memory_delete
from app.services.memory.patch import _memory_patch

from shared.models.openai import OpenAICompletionRequest
from shared.models.ledger import MemoryEntry
from shared.prompt_loader import load_prompt

from fastapi import HTTPException, status


def _get_all_memories_with_details():
    """Get all memories with their keywords, topics, and creation dates"""
    try:
        # Query database directly for all memories
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
            ORDER BY m.created_at DESC
        """)
        
        memory_details = []
        for row in cursor.fetchall():
            mem_id, memory_text, created_at, keywords_str, category = row
            keywords = set(keywords_str.split(',')) if keywords_str else set()
            
            memory_details.append({
                'id': mem_id,
                'memory': memory_text,
                'keywords': keywords,
                'category': category,
                'created_at': created_at
            })
        
        conn.close()
        return memory_details
    except Exception as e:
        logger.error(f"Error fetching all memories: {e}")
        return []


def _group_by_keyword_overlap(memories: List[Dict], min_matches: int) -> List[List[str]]:
    """Group memories by keyword overlap"""
    memory_groups = []
    processed = set()
    
    for i, mem1 in enumerate(memories):
        if mem1['id'] in processed:
            continue
            
        current_group = [mem1['id']]
        processed.add(mem1['id'])
        
        for j, mem2 in enumerate(memories[i+1:], i+1):
            if mem2['id'] in processed:
                continue
                
            # Count keyword overlap
            shared_keywords = mem1['keywords'].intersection(mem2['keywords'])
            if len(shared_keywords) >= min_matches:
                current_group.append(mem2['id'])
                processed.add(mem2['id'])
        
        if len(current_group) >= 2:  # Only include groups with multiple memories
            memory_groups.append(current_group)
    
    return memory_groups


def _group_by_timeframe(memories: List[Dict], timeframe_days: int) -> List[List[str]]:
    """Group memories by creation timeframe"""
    # Sort memories by creation date
    dated_memories = [m for m in memories if m.get('created_at')]
    dated_memories.sort(key=lambda x: x['created_at'])
    
    memory_groups = []
    current_group = []
    current_start = None
    
    for memory in dated_memories:
        try:
            created_date = datetime.fromisoformat(memory['created_at'].replace('Z', '+00:00'))
            
            if current_start is None:
                current_start = created_date
                current_group = [memory['id']]
            else:
                time_diff = created_date - current_start
                if time_diff.days <= timeframe_days:
                    current_group.append(memory['id'])
                else:
                    # Close current group and start new one
                    if len(current_group) >= 2:
                        memory_groups.append(current_group)
                    current_start = created_date
                    current_group = [memory['id']]
        except Exception as e:
            logger.error(f"Error parsing date for memory {memory['id']}: {e}")
            continue
    
    # Add final group
    if len(current_group) >= 2:
        memory_groups.append(current_group)
    
    return memory_groups


async def _memory_deduplicate(
    dry_run: bool = False,
    grouping_strategy: str = "topic_similarity",
    min_keyword_matches: int = 2,
    timeframe_days: int = 7
):
    """
    Main service function for memory deduplication.
    
    This is the exact logic from the original endpoint, just extracted into a service function.
    """
    # Validate grouping strategy
    valid_strategies = ["topic_similarity", "keyword_overlap", "timeframe"]
    if grouping_strategy not in valid_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid grouping strategy. Must be one of: {valid_strategies}"
        )

    result = []

    if grouping_strategy == "topic_similarity":
        # Original topic-based logic
        try:
            topics = _get_all_topics()
            
            if not topics:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No topics found in the ledger."
                )
        except Exception as e:
            logger.error(f"Error fetching topics: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch topics from the ledger."
            )

        # Create a mapping of topic_id to topic_name
        topic_map = {topic['id']: topic['name'] for topic in topics}

        if dry_run:
            # In dry-run mode, return estimation without making API calls
            return {
                "status": "dry_run",
                "grouping_strategy": grouping_strategy,
                "message": f"Would analyze {len(topics)} topics for similarity grouping",
                "topics": [{"id": t["id"], "name": t["name"]} for t in topics],
                "estimated_api_calls": 1 + len(topics)  # 1 for topic grouping + 1 per topic group
            }

        # Ask the LLM to select what topics are similar
        prompt = load_prompt("ledger", "memory", "dedup_topic_similarity", topic_map=str(topic_map))

        completion_request = OpenAICompletionRequest(
            model="gpt-4.1",
            prompt=prompt
        )

        api_port = os.getenv("API_PORT", 4200)

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                response = await client.post(f"http://api:{api_port}/v1/completions", json=completion_request.model_dump())
                response.raise_for_status()
                completion_response = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error fetching completion from API: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to fetch completion from the API: {str(e)}"
                )

            try:
                completion_text = completion_response['choices'][0]['content'].strip()
            except (KeyError, IndexError):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Invalid response format from LLM. Expected 'choices' with 'content', got: {completion_response}"
                )

            # Parse the completion text as JSON
            try:
                similar_topics = json.loads(completion_text)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid response format from LLM. Expected JSON array., got: {completion_text}"
                )

            # Process topic groups and get memory groups
            memory_groups = []
            for topic_ids in similar_topics:
                if not isinstance(topic_ids, list) or len(topic_ids) < 2:
                    continue
                
                # Get memories for these topics
                memory_ids = []
                for topic_id in topic_ids:
                    if topic_id not in topic_map:
                        continue
                    try:
                        mems = _get_memory_by_topic(topic_id)
                        memory_ids.extend(mems)
                    except HTTPException as e:
                        logger.error(f"Error fetching memories for topic {topic_id}: {str(e)}")
                        continue
                
                if len(memory_ids) >= 2:
                    memory_groups.append({
                        'memory_ids': memory_ids,
                        'group_name': f"Topics: {', '.join([topic_map.get(tid, tid) for tid in topic_ids])}"
                    })

    else:
        # Non-topic strategies: get all memories
        all_memories = _get_all_memories_with_details()
        
        if not all_memories:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No memories found."
            )

        if grouping_strategy == "keyword_overlap":
            memory_id_groups = _group_by_keyword_overlap(all_memories, min_keyword_matches)
            memory_groups = [
                {
                    'memory_ids': group,
                    'group_name': f"Keyword overlap group {i+1}"
                }
                for i, group in enumerate(memory_id_groups)
            ]

        elif grouping_strategy == "timeframe":
            memory_id_groups = _group_by_timeframe(all_memories, timeframe_days)
            memory_groups = [
                {
                    'memory_ids': group,
                    'group_name': f"Timeframe group {i+1} ({timeframe_days} days)"
                }
                for i, group in enumerate(memory_id_groups)
            ]

        if dry_run:
            return {
                "status": "dry_run",
                "grouping_strategy": grouping_strategy,
                "message": f"Would analyze {len(all_memories)} memories using {grouping_strategy} strategy",
                "total_memories": len(all_memories),
                "groups_found": len(memory_groups),
                "estimated_api_calls": len(memory_groups),  # 1 API call per group
                "parameters": {
                    "min_keyword_matches": min_keyword_matches if grouping_strategy == "keyword_overlap" else None,
                    "timeframe_days": timeframe_days if grouping_strategy == "timeframe" else None
                }
            }

    # Process memory groups (shared logic for all strategies)
    if not memory_groups:
        return {
            "status": "no_groups_found",
            "grouping_strategy": grouping_strategy,
            "message": "No memory groups found for deduplication."
        }

    api_port = os.getenv("API_PORT", 4200)
    async with httpx.AsyncClient(timeout=180) as client:
        for group_info in memory_groups:
            memory_ids = group_info['memory_ids']
            group_name = group_info['group_name']
            
            if not memory_ids:
                logger.warning(f"No memories found for group: {group_name}")
                continue
            
            # For each memory, get its full details
            memory_lines = []
            for mem_id in memory_ids:
                try:
                    mem_entry = _get_memory(mem_id)
                    # Format: id|memory_text|keywords|category
                    keywords_str = ",".join(mem_entry.keywords) if mem_entry.keywords else ""
                    memory_lines.append(f"{mem_id}|{mem_entry.memory}|{keywords_str}|{mem_entry.category or ''}")
                except Exception as e:
                    logger.error(f"Error fetching memory {mem_id}: {str(e)}")
                    continue
            
            if not memory_lines:
                logger.warning(f"No valid memories retrieved for group: {group_name}")
                continue
                
            # Combine all memory lines into a single string
            memory_block = "\n".join(memory_lines)

            prompt = load_prompt("ledger", "memory", "dedup_memories", memory_block=memory_block)
            
            dedup_request = OpenAICompletionRequest(
                model="gpt-4.1",
                prompt=prompt
            )
            
            try:
                response = await client.post(f"http://api:{api_port}/v1/completions", json=dedup_request.model_dump())
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error fetching completion from API: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to fetch completion from the API: {str(e)}"
                )

            try:
                text = data['choices'][0]['content'].strip()
            except (KeyError, IndexError):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Invalid response format from LLM. Expected 'choices' with 'content', got: {data}"
                )

            # Parse the completion text as JSON
            try:
                memory_updates = json.loads(text)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid response format from LLM. Expected JSON object, got: {text}"
                )

            # Validate response structure
            if not isinstance(memory_updates, dict):
                logger.warning(f"Invalid memory updates format: {memory_updates}")
                continue

            # process the updates
            update_success = True
            updated_memories = {}
            
            # if the update fails, don't delete any of the memories marked for deletion
            if 'update' in memory_updates and isinstance(memory_updates['update'], dict):
                for mem_id, update_data in memory_updates['update'].items():
                    try:
                        # Validate update data structure
                        if not isinstance(update_data, dict):
                            logger.warning(f"Invalid update data for memory {mem_id}: {update_data}")
                            continue
                        
                        # Create MemoryEntry for the update
                        memory_entry = MemoryEntry(
                            id=mem_id,
                            memory=update_data.get('memory'),
                            keywords=update_data.get('keywords', []),
                            category=update_data.get('category')
                        )
                        
                        _memory_patch(memory_entry)
                        updated_memories[mem_id] = update_data
                        logger.info(f"Successfully updated memory {mem_id}")
                        
                    except Exception as e:
                        update_success = False
                        logger.error(f"Failed to update memory {mem_id}: {str(e)}")
                        continue

            if not update_success:
                logger.error("Failed to update some memories. No deletions will be performed.")
                continue  # Skip deletion for this group, but continue with other groups

            deleted_memories = []
            if 'delete' in memory_updates and isinstance(memory_updates['delete'], list):
                for mem_id in memory_updates['delete']:
                    try:
                        _memory_delete(mem_id)
                        deleted_memories.append(mem_id)
                        logger.info(f"Successfully deleted memory {mem_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete memory {mem_id}: {str(e)}")
                        continue

            # Add the result to the final output
            result.append({
                "status": "completed",
                "grouping_strategy": grouping_strategy,
                "group": group_name,
                "updated_memories": updated_memories,
                "deleted_memories": deleted_memories
            })

    if not result:
        return {
            "status": "no_results",
            "grouping_strategy": grouping_strategy,
            "message": "No memory groups found or processed for deduplication."
        }
    
    logger.info(f"Deduplication completed for {len(result)} groups using {grouping_strategy} strategy.")
    logger.debug(f"Deduplication result: {result}")
    return result
