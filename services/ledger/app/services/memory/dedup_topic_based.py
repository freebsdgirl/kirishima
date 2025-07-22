"""
Service layer for topic-based memory deduplication operations.

This module provides business logic for topic-based memory deduplication system that:
1. Finds similar topics using semantic similarity on topic names
2. Consolidates similar topics by merging them (reassigning memories before deletion)
3. Deduplicates memories within consolidated topics, grouped by timeframe
"""

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import os
import httpx
import json
import sqlite3
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

from shared.models.openai import OpenAICompletionRequest
from shared.models.ledger import MemoryEntry, MemoryDedupResponse
from shared.prompt_loader import load_prompt
from app.util import _open_conn

from fastapi import HTTPException, status

# Try to import sentence-transformers for topic similarity
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    EMBEDDINGS_AVAILABLE = True
    logger.info("Sentence-transformers available for topic similarity")
except ImportError as e:
    EMBEDDINGS_AVAILABLE = False
    logger.warning(f"Sentence-transformers not available: {e}. Topic similarity disabled.")


@dataclass
class TopicInfo:
    """Information about a topic and its memories"""
    id: str
    name: str
    memory_count: int
    memory_ids: List[str]


@dataclass
class TopicGroup:
    """A group of similar topics that should be consolidated"""
    primary_topic: TopicInfo
    similar_topics: List[TopicInfo]
    similarity_score: float
    total_memories: int


@dataclass
class MemoryTimeChunk:
    """A time-based chunk of memories for LLM processing"""
    memories: List[Dict]  # Memory data with keywords, category
    timeframe_start: str
    timeframe_end: str
    topic_name: str
    estimated_tokens: int


@dataclass
class DeduplicationPlan:
    """Complete plan for topic-based deduplication"""
    topic_consolidations: List[TopicGroup]
    memory_chunks: List[MemoryTimeChunk]
    estimated_llm_requests: int
    estimated_total_tokens: int
    cost_breakdown: Dict[str, int]


def _get_all_topics_with_memories() -> List[TopicInfo]:
    """Get all topics with their memory counts and IDs"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT t.id, t.name, COUNT(mt.memory_id) as memory_count
        FROM topics t
        LEFT JOIN memory_topics mt ON t.id = mt.topic_id
        GROUP BY t.id, t.name
        HAVING memory_count > 0
        ORDER BY memory_count DESC
    """)
    
    topics = []
    for topic_id, name, memory_count in cursor.fetchall():
        # Get memory IDs for this topic
        cursor.execute("""
            SELECT memory_id FROM memory_topics WHERE topic_id = ?
        """, (topic_id,))
        memory_ids = [row[0] for row in cursor.fetchall()]
        
        topics.append(TopicInfo(
            id=topic_id,
            name=name,
            memory_count=memory_count,
            memory_ids=memory_ids
        ))
    
    conn.close()
    logger.info(f"Found {len(topics)} topics with memories")
    return topics


def _find_similar_topics(
    topics: List[TopicInfo], 
    similarity_threshold: float = 0.8,
    max_groups: int = 20
) -> List[TopicGroup]:
    """Find groups of similar topics using semantic similarity on names"""
    if not EMBEDDINGS_AVAILABLE or len(topics) < 2:
        return []
    
    try:
        # Load model for topic name similarity
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Get embeddings for topic names
        topic_names = [topic.name for topic in topics]
        embeddings = model.encode(topic_names)
        
        # Compute similarity matrix
        similarity_matrix = cosine_similarity(embeddings)
        
        # Find similar topic groups
        processed = set()
        topic_groups = []
        
        for i, topic in enumerate(topics):
            if i in processed or len(topic_groups) >= max_groups:
                continue
            
            # Find similar topics
            similar_indices = []
            for j in range(i + 1, len(topics)):
                if j in processed and similarity_matrix[i][j] >= similarity_threshold:
                    similar_indices.append(j)
            
            if similar_indices:
                similar_topics = [topics[j] for j in similar_indices]
                primary_topic = topic
                total_memories = topic.memory_count + sum(t.memory_count for t in similar_topics)
                avg_similarity = np.mean([similarity_matrix[i][j] for j in similar_indices])
                
                topic_groups.append(TopicGroup(
                    primary_topic=primary_topic,
                    similar_topics=similar_topics,
                    similarity_score=avg_similarity,
                    total_memories=total_memories
                ))
                
                # Mark as processed
                processed.add(i)
                for j in similar_indices:
                    processed.add(j)
        
        return sorted(topic_groups, key=lambda x: x.total_memories, reverse=True)
        
    except Exception as e:
        logger.error(f"Error finding similar topics: {e}")
        return []


def _create_memory_chunks(
    topic_info: TopicInfo,
    chunk_timeframe_hours: int = 24,
    max_memories_per_chunk: int = 50
) -> List[MemoryTimeChunk]:
    """Create time-based chunks of memories for a topic"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    # Get memories for this topic with creation times
    cursor.execute("""
        SELECT m.id, m.memory, m.created_at,
               GROUP_CONCAT(DISTINCT mt.tag) as keywords,
               mc.category
        FROM memories m
        JOIN memory_topics mto ON m.id = mto.memory_id
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN memory_category mc ON m.id = mc.memory_id
        WHERE mto.topic_id = ?
        GROUP BY m.id, m.memory, m.created_at, mc.category
        ORDER BY m.created_at ASC
    """, (topic_info.id,))
    
    memories = []
    for row in cursor.fetchall():
        mem_id, memory_text, created_at, keywords_str, category = row
        keywords = keywords_str.split(',') if keywords_str else []
        
        memories.append({
            'id': mem_id,
            'memory': memory_text,
            'created_at': created_at,
            'keywords': keywords,
            'category': category
        })
    
    conn.close()
    
    if not memories:
        return []
    
    # Group by time chunks
    chunks = []
    current_chunk = []
    chunk_start = None
    
    for memory in memories:
        if not memory['created_at']:
            continue
            
        try:
            created_at = datetime.fromisoformat(memory['created_at'].replace('Z', '+00:00'))
            
            if chunk_start is None:
                chunk_start = created_at
                current_chunk = [memory]
            else:
                time_diff = (created_at - chunk_start).total_seconds() / 3600  # hours
                
                if time_diff <= chunk_timeframe_hours and len(current_chunk) < max_memories_per_chunk:
                    current_chunk.append(memory)
                else:
                    # Finalize current chunk
                    if len(current_chunk) >= 2:
                        chunk_end = datetime.fromisoformat(current_chunk[-1]['created_at'].replace('Z', '+00:00'))
                        estimated_tokens = sum(len(m['memory'].split()) * 2 for m in current_chunk)
                        
                        chunks.append(MemoryTimeChunk(
                            memories=current_chunk,
                            timeframe_start=chunk_start.isoformat(),
                            timeframe_end=chunk_end.isoformat(),
                            topic_name=topic_info.name,
                            estimated_tokens=estimated_tokens
                        ))
                    
                    # Start new chunk
                    chunk_start = created_at
                    current_chunk = [memory]
                    
        except Exception as e:
            logger.error(f"Error parsing date for memory {memory['id']}: {e}")
            continue
    
    # Add final chunk
    if len(current_chunk) >= 2:
        chunk_end = datetime.fromisoformat(current_chunk[-1]['created_at'].replace('Z', '+00:00'))
        estimated_tokens = sum(len(m['memory'].split()) * 2 for m in current_chunk)
        
        chunks.append(MemoryTimeChunk(
            memories=current_chunk,
            timeframe_start=chunk_start.isoformat(),
            timeframe_end=chunk_end.isoformat(),
            topic_name=topic_info.name,
            estimated_tokens=estimated_tokens
        ))
    
    return chunks


def _get_memories_with_timestamps(topic_ids: List[str]) -> List[Dict]:
    """Get memory details with creation timestamps for topics"""
    from app.services.memory.get import _get_memory
    
    conn = _open_conn()
    cursor = conn.cursor()
    
    # Get all memory IDs for these topics with timestamps
    placeholders = ','.join(['?' for _ in topic_ids])
    cursor.execute(f"""
        SELECT DISTINCT mt.memory_id, m.created_at
        FROM memory_topics mt
        JOIN memories m ON mt.memory_id = m.id
        WHERE mt.topic_id IN ({placeholders})
        ORDER BY m.created_at
    """, topic_ids)
    
    memory_data = cursor.fetchall()
    conn.close()
    
    # Get full memory details with keywords
    memories = []
    for mem_id, created_timestamp in memory_data:
        try:
            mem = _get_memory(mem_id)
            memories.append({
                'id': mem_id,
                'memory': mem.memory,
                'keywords': mem.keywords,
                'category': mem.category,
                'created': created_timestamp
            })
        except Exception as e:
            logger.error(f"Error fetching memory {mem_id}: {e}")
    
    return memories


def _chunk_memories_by_timeframe(
    memories: List[Dict], 
    topic_name: str,
    max_memories_per_chunk: int = 15,
    chunk_days: int = 7
) -> List[MemoryTimeChunk]:
    """Group memories into time-based chunks for LLM processing"""
    
    if not memories:
        return []
    
    # Sort memories by creation time
    memories.sort(key=lambda x: x['created'])
    
    chunks = []
    current_chunk = []
    chunk_start_time = None
    
    for memory in memories:
        memory_time = datetime.fromisoformat(memory['created'].replace('Z', '+00:00'))
        
        if chunk_start_time is None:
            chunk_start_time = memory_time
            current_chunk = [memory]
        else:
            # Check if we should start a new chunk
            time_diff = memory_time - chunk_start_time
            should_new_chunk = (
                len(current_chunk) >= max_memories_per_chunk or 
                time_diff.days >= chunk_days
            )
            
            if should_new_chunk and current_chunk:
                # Complete current chunk
                chunk_end_time = datetime.fromisoformat(current_chunk[-1]['created'].replace('Z', '+00:00'))
                total_text = sum(len(mem['memory']) for mem in current_chunk)
                estimated_tokens = int(total_text / 3.5)  # Rough token estimate
                
                chunks.append(MemoryTimeChunk(
                    memories=current_chunk.copy(),
                    timeframe_start=chunk_start_time.isoformat(),
                    timeframe_end=chunk_end_time.isoformat(),
                    topic_name=topic_name,
                    estimated_tokens=estimated_tokens
                ))
                
                # Start new chunk
                chunk_start_time = memory_time
                current_chunk = [memory]
            else:
                current_chunk.append(memory)
    
    # Add final chunk if any memories remain
    if current_chunk:
        chunk_end_time = datetime.fromisoformat(current_chunk[-1]['created'].replace('Z', '+00:00'))
        total_text = sum(len(mem['memory']) for mem in current_chunk)
        estimated_tokens = int(total_text / 3.5)
        
        chunks.append(MemoryTimeChunk(
            memories=current_chunk,
            timeframe_start=chunk_start_time.isoformat(),
            timeframe_end=chunk_end_time.isoformat(),
            topic_name=topic_name,
            estimated_tokens=estimated_tokens
        ))
    
    return chunks


def _get_valid_categories() -> List[str]:
    """Get list of valid memory categories from database"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT category FROM memory_category WHERE category IS NOT NULL")
    categories = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return categories


def _create_deduplication_plan(
    topics: List[TopicInfo],
    topic_similarity_threshold: float = 0.8,
    max_topic_groups: int = 20,
    max_memory_chunks: int = 50,
    max_memories_per_chunk: int = 15,
    chunk_days: int = 7,
    max_total_tokens: int = 100000
) -> DeduplicationPlan:
    """Create a comprehensive deduplication plan"""
    
    # Step 1: Find similar topics for consolidation
    logger.info("Step 1: Finding similar topics for consolidation")
    topic_groups = _find_similar_topics(
        topics, 
        similarity_threshold=topic_similarity_threshold,
        max_groups=max_topic_groups
    )
    
    # Step 2: Create memory chunks for consolidated topics
    logger.info("Step 2: Creating memory chunks for timeframe-based deduplication")
    all_memory_chunks = []
    total_tokens = 0
    
    for topic_group in topic_groups:
        # Get consolidated topic name (use primary topic name)
        consolidated_topic_name = topic_group.primary_topic.name
        
        # Get all topic IDs in this group
        all_topic_ids = [topic_group.primary_topic.id] + [t.id for t in topic_group.similar_topics]
        
        # Get memories for these topics with timestamps
        memories = _get_memories_with_timestamps(all_topic_ids)
        
        if len(memories) > 1:  # Only process if there are multiple memories
            # Chunk memories by timeframe
            memory_chunks = _chunk_memories_by_timeframe(
                memories, 
                consolidated_topic_name,
                max_memories_per_chunk=max_memories_per_chunk,
                chunk_days=chunk_days
            )
            
            for chunk in memory_chunks:
                if total_tokens + chunk.estimated_tokens <= max_total_tokens:
                    all_memory_chunks.append(chunk)
                    total_tokens += chunk.estimated_tokens
                    
                    if len(all_memory_chunks) >= max_memory_chunks:
                        break
                
                if len(all_memory_chunks) >= max_memory_chunks or total_tokens >= max_total_tokens:
                    break
    
    # Calculate costs
    topic_consolidation_requests = len(topic_groups)
    memory_dedup_requests = len(all_memory_chunks)
    total_requests = topic_consolidation_requests + memory_dedup_requests
    
    cost_breakdown = {
        "topic_consolidations": topic_consolidation_requests,
        "memory_chunks": memory_dedup_requests,
        "total_requests": total_requests,
        "estimated_tokens": total_tokens
    }
    
    return DeduplicationPlan(
        topic_consolidations=topic_groups,
        memory_chunks=all_memory_chunks,
        estimated_llm_requests=total_requests,
        estimated_total_tokens=total_tokens,
        cost_breakdown=cost_breakdown
    )


async def _memory_deduplicate_topic_based(
    topic_similarity_threshold: float = 0.8,
    max_topic_groups: int = 20,
    max_memory_chunks: int = 50,
    max_memories_per_chunk: int = 15,
    chunk_days: int = 7,
    max_total_tokens: int = 100000,
    dry_run: bool = False
):
    """
    Topic-based memory deduplication service function.
    
    This is the exact logic from the original endpoint, just extracted into a service function.
    """
    logger.info(f"Starting topic-based memory deduplication (dry_run={dry_run})")
    
    # Get all topics with memories
    topics = _get_all_topics_with_memories()
    if not topics:
        return {
            "status": "no_topics",
            "message": "No topics with memories found"
        }
    
    # Create deduplication plan
    logger.info("Creating deduplication plan")
    plan = _create_deduplication_plan(
        topics=topics,
        topic_similarity_threshold=topic_similarity_threshold,
        max_topic_groups=max_topic_groups,
        max_memory_chunks=max_memory_chunks,
        max_memories_per_chunk=max_memories_per_chunk,
        chunk_days=chunk_days,
        max_total_tokens=max_total_tokens
    )
    
    if dry_run:
        # Return detailed cost analysis
        return {
            "status": "dry_run_complete",
            "plan": {
                "total_topics": len(topics),
                "topic_groups_to_consolidate": len(plan.topic_consolidations),
                "memory_chunks_to_deduplicate": len(plan.memory_chunks),
                "estimated_llm_requests": plan.estimated_llm_requests,
                "estimated_total_tokens": plan.estimated_total_tokens,
                "cost_breakdown": plan.cost_breakdown
            },
            "topic_consolidations": [
                {
                    "primary_topic": tg.primary_topic.name,
                    "similar_topics": [t.name for t in tg.similar_topics],
                    "total_memories": tg.total_memories,
                    "similarity_score": tg.similarity_score
                } for tg in plan.topic_consolidations
            ],
            "memory_chunks": [
                {
                    "topic_name": mc.topic_name,
                    "memory_count": len(mc.memories),
                    "timeframe": f"{mc.timeframe_start} to {mc.timeframe_end}",
                    "estimated_tokens": mc.estimated_tokens
                } for mc in plan.memory_chunks
            ]
        }
    
    # Execute plan
    logger.info("Executing topic consolidations")
    consolidation_results = await _consolidate_topics_with_llm(plan.topic_consolidations)
    
    # Apply topic merges FIRST (reassigning memories before deletion)
    topic_merge_summary = await _apply_topic_consolidations(consolidation_results)
    
    logger.info("Executing memory deduplication")
    deduplication_results = await _deduplicate_memory_chunks_with_llm(plan.memory_chunks)
    
    return {
        "status": "completed",
        "topic_consolidation_summary": topic_merge_summary,
        "memory_deduplication_summary": {
            "chunks_processed": len(deduplication_results),
            "total_updates": sum(r.get('update_count', 0) for r in deduplication_results),
            "total_deletions": sum(r.get('delete_count', 0) for r in deduplication_results)
        },
        "consolidation_details": consolidation_results,
        "deduplication_details": deduplication_results
    }


async def _consolidate_topics_with_llm(topic_groups: List[TopicGroup], dry_run: bool = False) -> List[Dict]:
    """Consolidate similar topics using LLM confirmation"""
    if dry_run:
        return [{"status": "dry_run", "group": i, "topics": len(tg.similar_topics) + 1} 
                for i, tg in enumerate(topic_groups)]
    
    results = []
    api_port = os.getenv("API_PORT", 4200)
    
    async with httpx.AsyncClient(timeout=180) as client:
        for i, topic_group in enumerate(topic_groups):
            logger.info(f"Consolidating topic group {i+1}/{len(topic_groups)}")
            
            # Prepare topic data for LLM
            primary_topic = topic_group.primary_topic.name
            similar_topics = [t.name for t in topic_group.similar_topics]
            all_topic_names = [primary_topic] + similar_topics
            all_topic_ids = [topic_group.primary_topic.id] + [t.id for t in topic_group.similar_topics]
            
            topic_list = "\n".join([f"- {name}" for name in all_topic_names])
            
            prompt = f"""The following topics appear to be similar and should potentially be consolidated:

{topic_list}

Please provide:
1. Whether these topics should actually be merged (they might be too different)
2. If merging, what the unified topic name should be (prefer the most descriptive name)

Respond in JSON format:
{{
    "should_merge": true/false,
    "unified_name": "Best topic name if merging",
    "reasoning": "Brief explanation"
}}"""

            request = OpenAICompletionRequest(
                model="gpt-4.1",
                prompt=prompt,
                temperature=0.3,
                max_tokens=500
            )
            
            try:
                response = await client.post(
                    f"http://api:{api_port}/v1/completions",
                    json=request.model_dump()
                )
                response.raise_for_status()
                data = response.json()
                
                llm_response = data['choices'][0]['content'].strip()
                try:
                    result = json.loads(llm_response)
                    result['group_index'] = i
                    result['original_topics'] = all_topic_names
                    result['original_topic_ids'] = all_topic_ids
                    results.append(result)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response for topic group {i}: {e}")
                    results.append({
                        "group_index": i,
                        "should_merge": False,
                        "error": "JSON parse error",
                        "original_topics": all_topic_names,
                        "original_topic_ids": all_topic_ids
                    })
                    
            except Exception as e:
                logger.error(f"Error consolidating topic group {i}: {e}")
                results.append({
                    "group_index": i,
                    "should_merge": False,
                    "error": str(e),
                    "original_topics": all_topic_names,
                    "original_topic_ids": all_topic_ids
                })
    
    return results


async def _deduplicate_memory_chunks_with_llm(memory_chunks: List[MemoryTimeChunk], dry_run: bool = False) -> List[Dict]:
    """Deduplicate memory chunks using LLM with category validation"""
    if dry_run:
        return [{"status": "dry_run", "chunk": i, "memories": len(mc.memories), "tokens": mc.estimated_tokens} 
                for i, mc in enumerate(memory_chunks)]
    
    # Get valid categories for validation
    valid_categories = _get_valid_categories()
    categories_str = ", ".join(valid_categories) if valid_categories else "No categories found"
    
    results = []
    api_port = os.getenv("API_PORT", 4200)
    
    async with httpx.AsyncClient(timeout=180) as client:
        for i, memory_chunk in enumerate(memory_chunks):
            logger.info(f"Deduplicating memory chunk {i+1}/{len(memory_chunks)} "
                       f"({len(memory_chunk.memories)} memories from {memory_chunk.timeframe_start} to {memory_chunk.timeframe_end})")
            
            # Prepare memory block
            memory_lines = []
            for mem in memory_chunk.memories:
                keywords_str = ",".join(mem['keywords']) if mem['keywords'] else ""
                memory_lines.append(f"{mem['id']}|{mem['memory']}|{keywords_str}|{mem['category'] or ''}")
            
            memory_block = "\n".join(memory_lines)
            
            prompt = f"""The following memories are from the topic "{memory_chunk.topic_name}" and were created between {memory_chunk.timeframe_start} and {memory_chunk.timeframe_end}.
Please deduplicate them carefully, consolidating similar content while preserving unique information.

IMPORTANT: Any category you assign must be exactly one of these valid categories: {categories_str}

{load_prompt("ledger", "memory", "dedup_memories", memory_block=memory_block)}"""
            
            request = OpenAICompletionRequest(
                model="gpt-4.1",
                prompt=prompt,
                temperature=0.7,
                max_tokens=2000
            )
            
            try:
                response = await client.post(
                    f"http://api:{api_port}/v1/completions",
                    json=request.model_dump()
                )
                response.raise_for_status()
                data = response.json()
                
                llm_response = data['choices'][0]['content'].strip()
                try:
                    memory_updates = json.loads(llm_response)
                    
                    # Validate categories in updates
                    if 'update' in memory_updates:
                        for mem_id, update_data in memory_updates['update'].items():
                            if 'category' in update_data:
                                category = update_data['category']
                                if category and category not in valid_categories:
                                    logger.warning(f"Invalid category '{category}' for memory {mem_id}, setting to None")
                                    update_data['category'] = None
                    
                    # Apply updates
                    result = await _apply_memory_updates(memory_updates, memory_chunk.topic_name)
                    result['chunk_index'] = i
                    result['timeframe'] = f"{memory_chunk.timeframe_start} to {memory_chunk.timeframe_end}"
                    result['topic_name'] = memory_chunk.topic_name
                    results.append(result)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response for memory chunk {i}: {e}")
                    results.append({
                        "chunk_index": i,
                        "error": "JSON parse error",
                        "topic_name": memory_chunk.topic_name,
                        "timeframe": f"{memory_chunk.timeframe_start} to {memory_chunk.timeframe_end}"
                    })
                    
            except Exception as e:
                logger.error(f"Error deduplicating memory chunk {i}: {e}")
                results.append({
                    "chunk_index": i,
                    "error": str(e),
                    "topic_name": memory_chunk.topic_name,
                    "timeframe": f"{memory_chunk.timeframe_start} to {memory_chunk.timeframe_end}"
                })
    
    return results


async def _apply_memory_updates(memory_updates: Dict, topic_name: str) -> Dict:
    """Apply memory updates and deletions, return summary"""
    from app.services.memory.delete import _memory_delete
    from app.services.memory.patch import _memory_patch
    
    updated_memories = {}
    deleted_memories = []
    
    # Apply updates first
    if 'update' in memory_updates and isinstance(memory_updates['update'], dict):
        for mem_id, update_data in memory_updates['update'].items():
            try:
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
                logger.error(f"Failed to update memory {mem_id}: {e}")
                return {
                    "error": f"Failed to update memory {mem_id}: {e}",
                    "topic_name": topic_name
                }
    
    # Apply deletions only if updates succeeded
    if 'delete' in memory_updates and isinstance(memory_updates['delete'], list):
        for mem_id in memory_updates['delete']:
            try:
                _memory_delete(mem_id)
                deleted_memories.append(mem_id)
                logger.info(f"Successfully deleted memory {mem_id}")
            except Exception as e:
                logger.error(f"Failed to delete memory {mem_id}: {e}")
    
    return {
        "updated_memories": updated_memories,
        "deleted_memories": deleted_memories,
        "update_count": len(updated_memories),
        "delete_count": len(deleted_memories),
        "topic_name": topic_name
    }


async def _apply_topic_consolidations(consolidation_results: List[Dict]) -> Dict:
    """Apply topic consolidations by merging topics and reassigning memories"""
    
    merged_count = 0
    skipped_count = 0
    total_moved_memories = 0
    total_deleted_topics = 0
    
    for result in consolidation_results:
        if result.get('should_merge', False) and 'error' not in result:
            try:
                # Extract consolidation info
                unified_name = result.get('unified_name', '')
                original_topic_ids = result.get('original_topic_ids', [])
                
                if len(original_topic_ids) < 2:
                    logger.warning(f"Skipping consolidation - need at least 2 topics, got {len(original_topic_ids)}")
                    skipped_count += 1
                    continue
                
                # Use first topic as primary, but update its name to the unified name
                primary_topic_id = original_topic_ids[0]
                merge_topic_ids = original_topic_ids[1:]
                
                # First, reassign all memories from topics-to-be-deleted to the primary topic
                conn = _open_conn()
                cursor = conn.cursor()
                
                moved_memories = 0
                for merge_topic_id in merge_topic_ids:
                    # Update memory_topics associations
                    cursor.execute("""
                        UPDATE memory_topics 
                        SET topic_id = ? 
                        WHERE topic_id = ? 
                        AND memory_id NOT IN (
                            SELECT memory_id FROM memory_topics WHERE topic_id = ?
                        )
                    """, (primary_topic_id, merge_topic_id, primary_topic_id))
                    moved_memories += cursor.rowcount
                    
                    # Remove duplicate associations (where memory was already linked to primary topic)
                    cursor.execute("""
                        DELETE FROM memory_topics 
                        WHERE topic_id = ? 
                        AND memory_id IN (
                            SELECT memory_id FROM memory_topics WHERE topic_id = ?
                        )
                    """, (merge_topic_id, primary_topic_id))
                
                # Update the primary topic name to the unified name
                cursor.execute("UPDATE topics SET name = ? WHERE id = ?", (unified_name, primary_topic_id))
                
                # Delete the merged topics
                for merge_topic_id in merge_topic_ids:
                    cursor.execute("DELETE FROM topics WHERE id = ?", (merge_topic_id,))
                
                conn.commit()
                conn.close()
                
                logger.info(f"Merged topics: {result.get('original_topics', [])} into '{unified_name}' (primary: {primary_topic_id})")
                logger.info(f"  Moved {moved_memories} memory associations")
                logger.info(f"  Deleted {len(merge_topic_ids)} topics")
                
                merged_count += 1
                total_moved_memories += moved_memories
                total_deleted_topics += len(merge_topic_ids)
                
            except Exception as e:
                logger.error(f"Failed to merge topics {result.get('original_topics', [])}: {e}")
                skipped_count += 1
        else:
            skipped_count += 1
    
    return {
        "merged_topic_groups": merged_count,
        "skipped_topic_groups": skipped_count,
        "total_moved_memories": total_moved_memories,
        "total_deleted_topics": total_deleted_topics
    }
