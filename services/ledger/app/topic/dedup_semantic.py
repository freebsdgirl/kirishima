"""
Semantic topic deduplication using sentence-transformers.

This module provides functionality to find and merge semantically similar topics,
consolidating their associated memories and reducing topic fragmentation.
"""

from fastapi import APIRouter, HTTPException, status
from shared.log_config import get_logger
from shared.models.openai import OpenAICompletionRequest
from shared.prompt_loader import load_prompt

import os
import httpx
import json
import sqlite3
import numpy as np
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
import asyncio

logger = get_logger(f"ledger.{__name__}")

router = APIRouter()

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
    centroid: Optional[np.ndarray] = None
    avg_similarity: float = 0.0
    density: float = 0.0

def _open_conn():
    """Open database connection with standard settings"""
    with open('/app/config/config.json') as f:
        config = json.load(f)
        db_path = config["db"]["ledger"]
    
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

class TopicSemanticDeduplicator:
    """Handles semantic similarity computation and clustering for topics"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = None
        self.model_name = model_name
        if EMBEDDINGS_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
                logger.info(f"Loaded sentence-transformer model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load sentence-transformer model: {e}")
                self.model = None
    
    def is_available(self) -> bool:
        """Check if semantic similarity is available"""
        return self.model is not None
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for a list of texts"""
        if not self.model:
            raise ValueError("Sentence-transformer model not available")
        
        if not texts:
            return np.array([])
        if len(texts) == 1:
            return self.model.encode(texts).reshape(1, -1)
        
        return self.model.encode(texts)
    
    def cluster_topics(
        self,
        topics: List[TopicWithEmbedding],
        similarity_threshold: float = 0.7,
        min_cluster_size: int = 2
    ) -> List[TopicCluster]:
        """Cluster topics by semantic similarity using DBSCAN"""
        if not topics or len(topics) < 2:
            return []
        
        # Extract embeddings
        embeddings = np.array([topic.embedding for topic in topics if topic.embedding is not None])
        if len(embeddings) == 0:
            return []
        
        # Convert similarity threshold to distance for DBSCAN (cosine distance = 1 - cosine similarity)
        eps = 1.0 - similarity_threshold
        
        # Perform clustering
        clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric='cosine')
        cluster_labels = clustering.fit_predict(embeddings)
        
        # Group topics by cluster
        clusters = defaultdict(list)
        for i, label in enumerate(cluster_labels):
            if label != -1:  # -1 indicates noise/no cluster
                clusters[label].append(topics[i])
        
        # Create TopicCluster objects
        result_clusters = []
        for cluster_topics in clusters.values():
            if len(cluster_topics) >= min_cluster_size:
                cluster = TopicCluster(topics=cluster_topics)
                cluster.centroid = np.mean([t.embedding for t in cluster_topics], axis=0)
                
                # Calculate average pairwise similarity
                if len(cluster_topics) > 1:
                    similarities = []
                    for i in range(len(cluster_topics)):
                        for j in range(i + 1, len(cluster_topics)):
                            sim = cosine_similarity(
                                cluster_topics[i].embedding.reshape(1, -1),
                                cluster_topics[j].embedding.reshape(1, -1)
                            )[0][0]
                            similarities.append(sim)
                    cluster.avg_similarity = np.mean(similarities)
                    cluster.density = cluster.avg_similarity
                
                result_clusters.append(cluster)
        
        # Sort by similarity/density
        result_clusters.sort(key=lambda c: c.density, reverse=True)
        
        logger.info(f"Found {len(result_clusters)} topic clusters from {len(topics)} topics")
        return result_clusters

def _get_topics_for_deduplication(min_memory_count: int = 1, max_topics: int = 100) -> List[TopicWithEmbedding]:
    """Get topics with their memory counts for deduplication"""
    conn = _open_conn()
    cursor = conn.cursor()
    
    # Get topics with memory counts
    cursor.execute("""
        SELECT t.id, t.name, t.created_at, COUNT(mt.memory_id) as memory_count
        FROM topics t
        LEFT JOIN memory_topics mt ON t.id = mt.topic_id
        GROUP BY t.id, t.name, t.created_at
        HAVING memory_count >= ?
        ORDER BY memory_count DESC, t.created_at DESC
        LIMIT ?
    """, (min_memory_count, max_topics))
    
    topics = []
    for row in cursor.fetchall():
        topic = TopicWithEmbedding(
            id=row[0],
            name=row[1],
            created_at=row[2],
            memory_count=row[3]
        )
        topics.append(topic)
    
    conn.close()
    logger.info(f"Found {len(topics)} topics for deduplication analysis")
    return topics

def _add_embeddings_to_topics(
    topics: List[TopicWithEmbedding],
    deduplicator: TopicSemanticDeduplicator
) -> List[TopicWithEmbedding]:
    """Add semantic embeddings to topic objects"""
    if not deduplicator.is_available():
        logger.warning("Semantic embeddings not available for topics")
        return topics
    
    try:
        topic_names = [topic.name for topic in topics]
        embeddings = deduplicator.get_embeddings(topic_names)
        
        for topic, embedding in zip(topics, embeddings):
            topic.embedding = embedding
        
        logger.info(f"Added embeddings to {len(topics)} topics")
        return topics
        
    except Exception as e:
        logger.error(f"Error computing topic embeddings: {e}")
        return topics

async def _merge_topics_llm(cluster: TopicCluster) -> Optional[Dict]:
    """Use LLM to decide how to merge similar topics"""
    api_port = os.getenv("API_PORT", 4200)
    
    # Prepare topic information
    topic_lines = []
    for topic in cluster.topics:
        topic_lines.append(f"{topic.id}|{topic.name}|{topic.memory_count} memories")
    
    topic_block = "\n".join(topic_lines)
    
    # Enhanced prompt for topic merging
    prompt = f"""The following topics have been identified as semantically similar (avg similarity: {cluster.avg_similarity:.2f}).
Please decide how to merge or consolidate them.

Topics to analyze:
{topic_block}

Instructions:
1. Choose the BEST topic name that represents all the topics
2. Return a JSON object with:
   - "primary_topic_id": ID of the topic to keep (choose the one with most memories or best name)
   - "primary_topic_name": The final name for the consolidated topic (may be modified)
   - "merge_topic_ids": Array of other topic IDs that should be merged into the primary
   - "reasoning": Brief explanation of the consolidation decision

Example output:
{{"primary_topic_id": "uuid-1", "primary_topic_name": "Consolidated Topic Name", "merge_topic_ids": ["uuid-2", "uuid-3"], "reasoning": "These topics all discuss the same concept"}}

JSON Response:"""

    request = OpenAICompletionRequest(
        model="gpt-4.1",
        prompt=prompt,
        temperature=0.3,
        max_tokens=1000,
        provider="openai"
    )
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(
                f"http://api:{api_port}/v1/completions",
                json=request.model_dump()
            )
            response.raise_for_status()
            data = response.json()
            
            text = data['choices'][0]['content'].strip()
            logger.info(f"LLM topic merge response: {text[:200]}...")
            
            try:
                merge_decision = json.loads(text)
                return merge_decision
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON for topic merge: {e}")
                logger.error(f"Raw content: {text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting LLM topic merge decision: {e}")
            return None

async def _apply_topic_merge(merge_decision: Dict) -> Dict:
    """Apply topic merge by moving memories and deleting old topics"""
    primary_id = merge_decision["primary_topic_id"]
    primary_name = merge_decision["primary_topic_name"]
    merge_ids = merge_decision["merge_topic_ids"]
    
    conn = _open_conn()
    cursor = conn.cursor()
    
    moved_memories = 0
    deleted_topics = []
    
    try:
        # Update primary topic name if changed
        cursor.execute("UPDATE topics SET name = ? WHERE id = ?", (primary_name, primary_id))
        
        # Move memories from merge topics to primary topic
        for topic_id in merge_ids:
            # Move memories
            cursor.execute("""
                UPDATE memory_topics 
                SET topic_id = ? 
                WHERE topic_id = ?
            """, (primary_id, topic_id))
            moved_memories += cursor.rowcount
            
            # Delete the old topic
            cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            if cursor.rowcount > 0:
                deleted_topics.append(topic_id)
                logger.info(f"Deleted topic {topic_id}")
        
        conn.commit()
        logger.info(f"Merged {len(merge_ids)} topics into {primary_id}, moved {moved_memories} memories")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error applying topic merge: {e}")
        raise
    finally:
        conn.close()
    
    return {
        "primary_topic_id": primary_id,
        "primary_topic_name": primary_name,
        "deleted_topics": deleted_topics,
        "moved_memories": moved_memories
    }

@router.post("/topics/_dedup_semantic")
async def deduplicate_topics_semantic(
    semantic_similarity_threshold: float = 0.7,
    min_cluster_size: int = 2,
    max_clusters_to_process: int = 10,
    min_memory_count: int = 1,
    max_topics: int = 100
):
    """
    Semantic-based topic deduplication using sentence-transformers.
    
    Args:
        semantic_similarity_threshold: Cosine similarity threshold for clustering (0.6-0.85)
        min_cluster_size: Minimum topics per cluster for LLM processing (2-4)
        max_clusters_to_process: Maximum clusters to send to LLM (5-15)
        min_memory_count: Minimum memories per topic to consider (1-5)
        max_topics: Maximum topics to analyze (50-200)
    """
    logger.info("Starting semantic-based topic deduplication")
    
    # Check if embeddings are available
    deduplicator = TopicSemanticDeduplicator()
    if not deduplicator.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sentence-transformers not available. Please install: pip install sentence-transformers scikit-learn"
        )
    
    # Get topics for analysis
    logger.info(f"Getting topics for analysis (max {max_topics})")
    topics = _get_topics_for_deduplication(min_memory_count=min_memory_count, max_topics=max_topics)
    
    if len(topics) < 2:
        return {
            "status": "no_candidates",
            "message": f"Need at least 2 topics for deduplication, found {len(topics)}"
        }
    
    # Add embeddings
    logger.info("Computing topic embeddings")
    topics_with_embeddings = _add_embeddings_to_topics(topics, deduplicator)
    
    # Cluster topics
    logger.info("Clustering topics by semantic similarity")
    clusters = deduplicator.cluster_topics(
        topics_with_embeddings,
        similarity_threshold=semantic_similarity_threshold,
        min_cluster_size=min_cluster_size
    )
    
    if not clusters:
        return {
            "status": "no_clusters",
            "message": f"No topic clusters found with similarity >= {semantic_similarity_threshold}"
        }
    
    # Process clusters with LLM
    logger.info(f"Processing {min(len(clusters), max_clusters_to_process)} clusters with LLM")
    results = []
    
    for i, cluster in enumerate(clusters[:max_clusters_to_process]):
        logger.info(f"Processing topic cluster {i+1}: {len(cluster.topics)} topics, density={cluster.density:.3f}")
        
        merge_decision = await _merge_topics_llm(cluster)
        if merge_decision:
            try:
                merge_result = await _apply_topic_merge(merge_decision)
                results.append({
                    "cluster_index": i,
                    "cluster_size": len(cluster.topics),
                    "semantic_density": float(cluster.density),
                    "avg_similarity": float(cluster.avg_similarity),
                    "merge_decision": merge_decision,
                    "merge_result": merge_result
                })
            except Exception as e:
                logger.error(f"Failed to apply topic merge for cluster {i}: {e}")
                continue
    
    # Summary
    total_topics_merged = sum(len(r["merge_result"]["deleted_topics"]) for r in results)
    total_memories_moved = sum(r["merge_result"]["moved_memories"] for r in results)
    
    return {
        "status": "completed",
        "topic_dedup_results": {
            "processed_clusters": len(results),
            "results": results
        },
        "stats": {
            "topics_analyzed": len(topics),
            "semantic_clusters_found": len(clusters),
            "clusters_processed": len(results),
            "topics_merged": total_topics_merged,
            "memories_moved": total_memories_moved,
            "config": {
                "semantic_similarity_threshold": semantic_similarity_threshold,
                "min_cluster_size": min_cluster_size,
                "min_memory_count": min_memory_count
            }
        }
    }

@router.get("/topics/_dedup_semantic/preview")
async def preview_topic_deduplication_semantic(
    semantic_similarity_threshold: float = 0.7,
    min_cluster_size: int = 2,
    max_clusters_to_process: int = 10,
    min_memory_count: int = 1,
    max_topics: int = 100
):
    """Preview what topics would be processed in semantic deduplication"""
    logger.info("Previewing semantic topic deduplication")
    
    deduplicator = TopicSemanticDeduplicator()
    if not deduplicator.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sentence-transformers not available"
        )
    
    topics = _get_topics_for_deduplication(min_memory_count=min_memory_count, max_topics=max_topics)
    
    if len(topics) < 2:
        return {
            "status": "no_candidates",
            "message": f"Need at least 2 topics for deduplication, found {len(topics)}"
        }
    
    topics_with_embeddings = _add_embeddings_to_topics(topics, deduplicator)
    clusters = deduplicator.cluster_topics(
        topics_with_embeddings,
        similarity_threshold=semantic_similarity_threshold,
        min_cluster_size=min_cluster_size
    )
    
    preview_clusters = []
    for i, cluster in enumerate(clusters[:max_clusters_to_process]):
        cluster_preview = {
            "cluster_index": i,
            "topic_count": len(cluster.topics),
            "density": float(cluster.density),
            "avg_similarity": float(cluster.avg_similarity),
            "topics": [
                {
                    "id": topic.id,
                    "name": topic.name,
                    "memory_count": topic.memory_count,
                    "created_at": topic.created_at
                }
                for topic in cluster.topics
            ]
        }
        preview_clusters.append(cluster_preview)
    
    return {
        "status": "preview",
        "total_topics": len(topics),
        "semantic_clusters_found": len(clusters),
        "clusters_that_would_be_processed": min(len(clusters), max_clusters_to_process),
        "preview_clusters": preview_clusters,
        "config": {
            "semantic_similarity_threshold": semantic_similarity_threshold,
            "min_cluster_size": min_cluster_size,
            "min_memory_count": min_memory_count
        }
    }
