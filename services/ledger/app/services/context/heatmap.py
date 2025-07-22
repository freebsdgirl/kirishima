"""
Heatmap service for tracking keyword relevance and memory scoring.

This service manages a dynamic keyword heatmap that tracks the relevance of keywords
over time and scores memories based on their keyword matches.

The system works as follows:
1. Keywords are assigned weights (high=1.0, medium=0.7, low=0.5)
2. Keyword scores adjust over time based on usage patterns
3. Memories are scored based on matching keywords from the heatmap
4. Unused keywords decay and are eventually removed
"""

import sqlite3
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from app.util import _open_conn
from shared.log_config import get_logger

logger = get_logger(f"ledger.{__name__}")

# Configuration for keyword scoring - adjust these values as needed
DEFAULT_SCORES = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.5
}

# How much to adjust existing scores towards new weight (lower = more gradual)
ADJUSTMENT_FACTOR = 0.1  # Very gradual adjustment

# How much to decay unused keywords each update
DECAY_RATE = 0.05

# Minimum score before removal from heatmap
MIN_SCORE = 0.1

# How much to adjust scores when keywords stay the same weight (minimal drift)
SAME_WEIGHT_ADJUSTMENT = 0.02


async def update_heatmap(keywords_with_weights: Dict[str, str]) -> Dict[str, any]:
    """
    Update the keyword heatmap with new weighted keywords and recalculate memory scores.
    
    Args:
        keywords_with_weights: Dictionary mapping keywords to their weights ("high", "medium", "low")
        
    Returns:
        Dictionary containing update statistics and affected memory count
    """
    try:
        conn = _open_conn()
        cursor = conn.cursor()
        
        # Get current timestamp
        now = datetime.now().isoformat()
        
        # Get all existing keywords
        cursor.execute("SELECT keyword, score, last_updated FROM heatmap_score")
        existing_keywords = {row[0]: {"score": row[1], "last_updated": row[2]} for row in cursor.fetchall()}
        
        updated_keywords = []
        new_keywords = []
        
        # Process incoming keywords
        for keyword, weight in keywords_with_weights.items():
            if weight not in DEFAULT_SCORES:
                logger.warning(f"Unknown weight '{weight}' for keyword '{keyword}', skipping")
                continue
                
            target_score = DEFAULT_SCORES[weight]
            
            if keyword in existing_keywords:
                # Adjust existing keyword score towards target
                current_score = existing_keywords[keyword]["score"]
                
                # If the weight is the same as what would produce the current score, 
                # apply minimal adjustment to prevent drift
                if abs(current_score - target_score) < 0.1:
                    new_score = current_score + (target_score - current_score) * SAME_WEIGHT_ADJUSTMENT
                else:
                    # Apply normal adjustment for weight changes
                    new_score = current_score + (target_score - current_score) * ADJUSTMENT_FACTOR
                
                new_score = max(MIN_SCORE, min(1.0, new_score))  # Clamp between MIN_SCORE and 1.0
                
                cursor.execute(
                    "UPDATE heatmap_score SET score = ?, last_updated = ? WHERE keyword = ?",
                    (new_score, now, keyword)
                )
                updated_keywords.append(keyword)
                existing_keywords[keyword]["score"] = new_score  # Update for decay processing
            else:
                # Add new keyword
                cursor.execute(
                    "INSERT INTO heatmap_score (keyword, score, last_updated) VALUES (?, ?, ?)",
                    (keyword, target_score, now)
                )
                new_keywords.append(keyword)
        
        # Decay keywords not mentioned in this update
        mentioned_keywords = set(keywords_with_weights.keys())
        decayed_keywords = []
        removed_keywords = []
        
        for keyword, data in existing_keywords.items():
            if keyword not in mentioned_keywords:
                new_score = data["score"] - DECAY_RATE
                if new_score <= MIN_SCORE:
                    # Remove keyword and its memory associations
                    cursor.execute("DELETE FROM heatmap_score WHERE keyword = ?", (keyword,))
                    removed_keywords.append(keyword)
                else:
                    cursor.execute(
                        "UPDATE heatmap_score SET score = ?, last_updated = ? WHERE keyword = ?",
                        (new_score, now, keyword)
                    )
                    decayed_keywords.append(keyword)
        
        # Recalculate memory scores
        affected_memories = await _recalculate_memory_scores(cursor)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Heatmap updated: {len(new_keywords)} new, {len(updated_keywords)} updated, "
                   f"{len(decayed_keywords)} decayed, {len(removed_keywords)} removed keywords. "
                   f"{affected_memories} memories rescored.")
        
        return {
            "new_keywords": new_keywords,
            "updated_keywords": updated_keywords,
            "decayed_keywords": decayed_keywords,
            "removed_keywords": removed_keywords,
            "affected_memories": affected_memories
        }
        
    except Exception as e:
        logger.error(f"Error updating heatmap: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise


async def _recalculate_memory_scores(cursor: sqlite3.Cursor) -> int:
    """
    Recalculate scores for all memories based on current heatmap values.
    
    Args:
        cursor: Database cursor for the current transaction
        
    Returns:
        Number of memories that were rescored
    """
    try:
        # Clear existing memory scores
        cursor.execute("DELETE FROM heatmap_memories")
        
        # Get all current heatmap keywords and their scores
        cursor.execute("SELECT keyword, score FROM heatmap_score")
        keyword_scores = dict(cursor.fetchall())
        
        if not keyword_scores:
            return 0
        
        # Get all memories with their keywords (tags)
        cursor.execute("""
            SELECT DISTINCT m.id, m.memory
            FROM memories m
            JOIN memory_tags mt ON m.id = mt.memory_id
            WHERE mt.tag IN ({})
        """.format(','.join('?' * len(keyword_scores))), list(keyword_scores.keys()))
        
        memories_with_keywords = cursor.fetchall()
        
        memory_scores = {}
        
        # Calculate score for each memory
        for memory_id, memory_text in memories_with_keywords:
            # Get all tags for this memory
            cursor.execute("SELECT tag FROM memory_tags WHERE memory_id = ?", (memory_id,))
            memory_tags = [row[0] for row in cursor.fetchall()]
            
            # Calculate total score from matching keywords
            total_score = 0.0
            for tag in memory_tags:
                if tag in keyword_scores:
                    total_score += keyword_scores[tag]
            
            if total_score > 0:
                memory_scores[memory_id] = total_score
        
        # Insert memory scores
        now = datetime.now().isoformat()
        for memory_id, score in memory_scores.items():
            cursor.execute(
                "INSERT INTO heatmap_memories (memory_id, score, last_updated) VALUES (?, ?, ?)",
                (memory_id, score, now)
            )
        
        return len(memory_scores)
        
    except Exception as e:
        logger.error(f"Error recalculating memory scores: {e}")
        raise


async def get_top_memories_by_heatmap(limit: int = 10) -> List[Dict[str, any]]:
    """
    Get the top-scored memories from the heatmap.
    
    Args:
        limit: Maximum number of memories to return
        
    Returns:
        List of memories with their scores, ordered by score descending
    """
    try:
        conn = _open_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.id, m.memory, m.created_at, hm.score, hm.last_updated
            FROM memories m
            JOIN heatmap_memories hm ON m.id = hm.memory_id
            ORDER BY hm.score DESC
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "memory": row[1],
                "created_at": row[2],
                "heatmap_score": row[3],
                "score_updated": row[4]
            })
        
        conn.close()
        return results
        
    except Exception as e:
        logger.error(f"Error getting top memories by heatmap: {e}")
        raise


async def get_keyword_scores() -> Dict[str, float]:
    """
    Get current keyword scores from the heatmap.
    
    Returns:
        Dictionary mapping keywords to their current scores
    """
    try:
        conn = _open_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT keyword, score FROM heatmap_score ORDER BY score DESC")
        scores = dict(cursor.fetchall())
        
        conn.close()
        return scores
        
    except Exception as e:
        logger.error(f"Error getting keyword scores: {e}")
        raise
