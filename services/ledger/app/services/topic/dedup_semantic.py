"""
Service layer for semantic topic deduplication operations.

This module provides business logic for finding and merging semantically similar topics.
"""

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import os
import httpx
import json
import sqlite3
import numpy as np
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
import asyncio

from shared.models.openai import OpenAICompletionRequest
from shared.prompt_loader import load_prompt
from app.util import _open_conn

from fastapi import HTTPException, status

# Try to import sentence-transformers, fall back gracefully
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import DBSCAN
    EMBEDDINGS_AVAILABLE = True
    logger.info("Sentence-transformers available for topic deduplication")
except ImportError as e:
    EMBEDDINGS_AVAILABLE = False
    logger.warning(f"Sentence-transformers not available: {e}")

@dataclass
class TopicWithEmbedding:
    """Topic with semantic embedding and memory count"""
    id: str
    name: str
    created_at: str
    memory_count: int
    embedding: Optional[np.ndarray] = None

@dataclass
class TopicCluster:
    """A cluster of semantically similar topics"""
    topics: List[TopicWithEmbedding]
    merged_id: Optional[str] = None
    merged_name: Optional[str] = None
    memory_count: int = 0


def _get_topics_with_memory_counts() -> List[TopicWithEmbedding]:
    """Get all topics with their memory counts"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT t.id, t.name, t.created_at, COUNT(mt.memory_id) as memory_count
        FROM topics t
        LEFT JOIN memory_topics mt ON t.id = mt.topic_id
        GROUP BY t.id, t.name, t.created_at
        HAVING memory_count > 0
        ORDER BY memory_count DESC, t.created_at ASC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    topics = []
    for row in rows:
        topic_id, name, created_at, memory_count = row
        topics.append(TopicWithEmbedding(
            id=topic_id,
            name=name,
            created_at=created_at,
            memory_count=memory_count
        ))
    
    return topics


def _generate_embeddings(topics: List[TopicWithEmbedding]) -> None:
    """Generate embeddings for topic names using sentence-transformers"""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sentence-transformers library is not available. Install with: pip install sentence-transformers scikit-learn"
        )
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    topic_names = [topic.name for topic in topics]
    embeddings = model.encode(topic_names, convert_to_numpy=True)
    
    for topic, embedding in zip(topics, embeddings):
        topic.embedding = embedding


def _find_similar_topic_clusters(topics: List[TopicWithEmbedding], 
                                similarity_threshold: float,
                                max_clusters: int) -> List[TopicCluster]:
    """Find clusters of similar topics using DBSCAN clustering"""
    if not topics or not all(t.embedding is not None for t in topics):
        return []
    
    embeddings = np.array([topic.embedding for topic in topics])
    
    # Calculate similarity matrix and convert to distance matrix
    similarity_matrix = cosine_similarity(embeddings)
    distance_matrix = 1 - similarity_matrix
    
    # Use DBSCAN clustering with distance threshold
    eps = 1 - similarity_threshold  # Convert similarity to distance
    clustering = DBSCAN(eps=eps, min_samples=2, metric='precomputed')
    cluster_labels = clustering.fit_predict(distance_matrix)
    
    # Group topics by cluster
    clusters_dict = defaultdict(list)
    for idx, label in enumerate(cluster_labels):
        if label != -1:  # -1 indicates noise (unclustered points)
            clusters_dict[label].append(topics[idx])
    
    # Convert to TopicCluster objects and sort by total memory count
    clusters = []
    for topics_in_cluster in clusters_dict.values():
        if len(topics_in_cluster) >= 2:
            cluster = TopicCluster(
                topics=sorted(topics_in_cluster, key=lambda t: t.memory_count, reverse=True),
                memory_count=sum(t.memory_count for t in topics_in_cluster)
            )
            clusters.append(cluster)
    
    # Sort clusters by total memory count and limit
    clusters.sort(key=lambda c: c.memory_count, reverse=True)
    return clusters[:max_clusters]


async def _consolidate_topics_with_llm(cluster: TopicCluster) -> Dict:
    """Use LLM to determine the best consolidated topic name"""
    topic_info = []
    for topic in cluster.topics:
        topic_info.append({
            'name': topic.name,
            'memory_count': topic.memory_count,
            'created_at': topic.created_at
        })
    
    # Load prompt template
    prompt_content = load_prompt("ledger/topic/dedup_semantic.j2", {
        'topics': topic_info,
        'total_memories': cluster.memory_count
    })
    
    request = OpenAICompletionRequest(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt_content}
        ],
        temperature=0.1,
        max_tokens=300
    )
    
    proxy_url = os.getenv("PROXY_URL", "http://proxy:8003")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{proxy_url}/singleturn",
                json=request.model_dump()
            )
            response.raise_for_status()
            result = response.json()
            
            assistant_content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Parse JSON response
            try:
                consolidation_data = json.loads(assistant_content)
                return consolidation_data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response as JSON: {assistant_content}")
                # Fallback: use the topic with most memories
                primary_topic = cluster.topics[0]  # Already sorted by memory count
                return {
                    "consolidated_name": primary_topic.name,
                    "primary_topic_id": primary_topic.id,
                    "reasoning": "LLM response parsing failed, using topic with most memories"
                }
                
    except Exception as e:
        logger.error(f"LLM consolidation failed: {e}")
        # Fallback: use the topic with most memories
        primary_topic = cluster.topics[0]
        return {
            "consolidated_name": primary_topic.name,
            "primary_topic_id": primary_topic.id,
            "reasoning": f"LLM call failed: {str(e)}"
        }


def _reassign_memories_to_primary_topic(cluster: TopicCluster, primary_topic_id: str) -> int:
    """Reassign all memories from secondary topics to the primary topic"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    secondary_topic_ids = [t.id for t in cluster.topics if t.id != primary_topic_id]
    total_reassigned = 0
    
    try:
        for topic_id in secondary_topic_ids:
            # Get memories for this topic
            cursor.execute("SELECT memory_id FROM memory_topics WHERE topic_id = ?", (topic_id,))
            memory_rows = cursor.fetchall()
            
            for (memory_id,) in memory_rows:
                # Check if memory already associated with primary topic
                cursor.execute(
                    "SELECT 1 FROM memory_topics WHERE memory_id = ? AND topic_id = ?",
                    (memory_id, primary_topic_id)
                )
                exists = cursor.fetchone()
                
                if not exists:
                    # Add association with primary topic
                    cursor.execute(
                        "INSERT INTO memory_topics (memory_id, topic_id) VALUES (?, ?)",
                        (memory_id, primary_topic_id)
                    )
                    total_reassigned += 1
                
                # Remove association with secondary topic
                cursor.execute(
                    "DELETE FROM memory_topics WHERE memory_id = ? AND topic_id = ?",
                    (memory_id, topic_id)
                )
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to reassign memories for cluster: {e}")
        raise
    finally:
        conn.close()
    
    return total_reassigned


def _delete_empty_topics(cluster: TopicCluster, primary_topic_id: str) -> int:
    """Delete secondary topics that no longer have any memories"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    secondary_topic_ids = [t.id for t in cluster.topics if t.id != primary_topic_id]
    deleted_count = 0
    
    try:
        for topic_id in secondary_topic_ids:
            # Verify topic has no memories
            cursor.execute("SELECT COUNT(*) FROM memory_topics WHERE topic_id = ?", (topic_id,))
            count = cursor.fetchone()[0]
            
            if count == 0:
                cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
                deleted_count += 1
                logger.info(f"Deleted empty topic: {topic_id}")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to delete empty topics: {e}")
        raise
    finally:
        conn.close()
    
    return deleted_count


def _update_primary_topic_name(topic_id: str, new_name: str) -> None:
    """Update the name of the primary topic"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE topics SET name = ? WHERE id = ?", (new_name, topic_id))
        conn.commit()
        logger.info(f"Updated topic {topic_id} name to: {new_name}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update topic name: {e}")
        raise
    finally:
        conn.close()


async def _process_topic_cluster(cluster: TopicCluster) -> Dict:
    """Process a single topic cluster - consolidate and merge"""
    
    # Get LLM recommendation for consolidation
    consolidation = await _consolidate_topics_with_llm(cluster)
    primary_topic_id = consolidation.get('primary_topic_id')
    consolidated_name = consolidation.get('consolidated_name')
    
    if not primary_topic_id:
        # Fallback: use topic with most memories
        primary_topic_id = cluster.topics[0].id
        consolidated_name = cluster.topics[0].name
    
    # Track original state
    original_topic_names = [t.name for t in cluster.topics]
    
    # Reassign memories from secondary topics to primary
    reassigned_count = _reassign_memories_to_primary_topic(cluster, primary_topic_id)
    
    # Delete empty secondary topics
    deleted_count = _delete_empty_topics(cluster, primary_topic_id)
    
    # Update primary topic name if different
    primary_topic = next(t for t in cluster.topics if t.id == primary_topic_id)
    if consolidated_name and consolidated_name != primary_topic.name:
        _update_primary_topic_name(primary_topic_id, consolidated_name)
    
    cluster.merged_id = primary_topic_id
    cluster.merged_name = consolidated_name or primary_topic.name
    
    return {
        'cluster_id': f"cluster_{primary_topic_id}",
        'primary_topic_id': primary_topic_id,
        'consolidated_name': cluster.merged_name,
        'original_topics': [{'id': t.id, 'name': t.name, 'memory_count': t.memory_count} for t in cluster.topics],
        'total_memories': cluster.memory_count,
        'memories_reassigned': reassigned_count,
        'topics_deleted': deleted_count,
        'llm_reasoning': consolidation.get('reasoning', 'No reasoning provided')
    }


async def _topic_deduplicate_semantic(
    similarity_threshold: float,
    max_clusters: int,
    dry_run: bool
) -> Dict:
    """
    Main function for semantic topic deduplication.
    
    Process:
    1. Get all topics with their memory counts
    2. Generate embeddings for topic names using sentence-transformers
    3. Use DBSCAN clustering to find similar topics
    4. For each cluster, use LLM to determine the best consolidated name
    5. Reassign memories from secondary topics to primary topic
    6. Delete empty secondary topics
    
    Args:
        similarity_threshold: Cosine similarity threshold for topic grouping (0.7-0.9)
        max_clusters: Maximum number of topic clusters to process (5-20)
        dry_run: If True, only analyze and return what would be done without making changes
    
    Returns:
        Dict: Results of the semantic topic deduplication operation
    """
    
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sentence-transformers library is not available. Install with: pip install sentence-transformers scikit-learn"
        )
    
    # Get topics with memory counts
    topics = _get_topics_with_memory_counts()
    
    if not topics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No topics with memories found"
        )
    
    logger.info(f"Found {len(topics)} topics with memories")
    
    # Generate embeddings
    _generate_embeddings(topics)
    
    # Find similar topic clusters
    clusters = _find_similar_topic_clusters(topics, similarity_threshold, max_clusters)
    
    if not clusters:
        return {
            'status': 'no_clusters_found',
            'message': f'No similar topic clusters found with threshold {similarity_threshold}',
            'total_topics': len(topics),
            'clusters_found': 0
        }
    
    logger.info(f"Found {len(clusters)} similar topic clusters")
    
    if dry_run:
        # Estimate what would be done
        estimated_operations = []
        for i, cluster in enumerate(clusters):
            estimated_operations.append({
                'cluster_id': f'cluster_{i+1}',
                'topics_to_merge': [{'id': t.id, 'name': t.name, 'memory_count': t.memory_count} for t in cluster.topics],
                'total_memories': cluster.memory_count,
                'estimated_topics_to_delete': len(cluster.topics) - 1
            })
        
        return {
            'status': 'dry_run',
            'message': f'Would process {len(clusters)} topic clusters',
            'total_topics': len(topics),
            'clusters_found': len(clusters),
            'similarity_threshold': similarity_threshold,
            'estimated_operations': estimated_operations
        }
    
    # Process clusters
    results = []
    for cluster in clusters:
        try:
            result = await _process_topic_cluster(cluster)
            results.append(result)
            logger.info(f"Successfully processed cluster with {len(cluster.topics)} topics")
        except Exception as e:
            logger.error(f"Failed to process cluster with topics {[t.name for t in cluster.topics]}: {e}")
            continue
    
    if not results:
        return {
            'status': 'no_results',
            'message': 'No topic clusters were successfully processed',
            'total_topics': len(topics),
            'clusters_found': len(clusters)
        }
    
    total_deleted = sum(r['topics_deleted'] for r in results)
    total_reassigned = sum(r['memories_reassigned'] for r in results)
    
    logger.info(f"Semantic topic deduplication completed: {len(results)} clusters processed, {total_deleted} topics deleted, {total_reassigned} memories reassigned")
    
    return {
        'status': 'completed',
        'message': f'Successfully processed {len(results)} topic clusters',
        'total_topics': len(topics),
        'clusters_processed': len(results),
        'total_topics_deleted': total_deleted,
        'total_memories_reassigned': total_reassigned,
        'similarity_threshold': similarity_threshold,
        'results': results
    }
