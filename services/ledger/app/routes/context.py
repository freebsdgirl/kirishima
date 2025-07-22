"""
Contextual Memory and Heatmap API Routes
This module defines FastAPI routes for managing and querying a dynamic keyword heatmap
used to track contextual relevance of memories in conversations. The endpoints allow
clients to retrieve contextually relevant memories, update the heatmap with new keyword
weights, fetch top-scored memories, and inspect current keyword scores.
Endpoints:
    - GET /: Retrieve the most relevant memory content strings based on heatmap scores.
    - POST /update_heatmap: Update the heatmap with weighted keywords from the current conversation.
    - GET /top_memories: Get top-scored memories with their heatmap scores.
    - GET /keyword_scores: Get all current keyword scores from the heatmap.
All endpoints include input validation and error handling, and log key actions for
monitoring and debugging.
"""

from fastapi import APIRouter, HTTPException

from app.services.context.heatmap import update_heatmap, get_top_memories_by_heatmap, get_keyword_scores

from shared.models.ledger import HeatmapUpdateRequest, HeatmapUpdateResponse, TopMemoriesResponse, KeywordScoresResponse, ContextMemoriesResponse

from shared.log_config import get_logger

logger = get_logger(f"ledger.{__name__}")

router = APIRouter()


@router.get("/", response_model=ContextMemoriesResponse)
async def get_context_memories(limit: int = 10):
    """
    Get contextually relevant memories based on current heatmap scores.
    
    Returns the top-scoring memories from the heatmap system, providing
    the most relevant memories for the current conversation context.
    Only returns the memory content strings, not metadata.
    
    Args:
        limit: Maximum number of memories to return (default: 10, max: 50)
        
    Returns:
        List of memory content strings ordered by relevance
    """
    try:
        if limit <= 0 or limit > 50:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 50")
        
        # Get top memories from heatmap
        top_memories = await get_top_memories_by_heatmap(limit)
        
        # Extract just the memory content
        memory_contents = [memory["memory"] for memory in top_memories]
        
        logger.info(f"Retrieved {len(memory_contents)} contextual memories")
        
        return ContextMemoriesResponse(memories=memory_contents)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_context_memories endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/update_heatmap", response_model=HeatmapUpdateResponse)
async def update_keyword_heatmap(request: HeatmapUpdateRequest):
    """
    Update the keyword heatmap with weighted keywords from the current conversation.
    
    This endpoint processes a set of keywords with their assigned weights (high/medium/low)
    and updates the dynamic heatmap. The heatmap tracks keyword relevance over time:
    - New keywords are added with their initial scores
    - Existing keywords are adjusted towards the new weight
    - Unused keywords decay over time
    - Memories are rescored based on updated keyword values
    
    Args:
        request: Contains keywords mapped to their weights
        
    Returns:
        Update statistics including affected keywords and memories
    """
    try:
        if not request.keywords:
            raise HTTPException(status_code=400, detail="Keywords dictionary cannot be empty")
        
        # Validate weights
        valid_weights = {"high", "medium", "low"}
        for keyword, weight in request.keywords.items():
            if weight not in valid_weights:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid weight '{weight}' for keyword '{keyword}'. Must be one of: {valid_weights}"
                )
        
        logger.info(f"Updating heatmap with {len(request.keywords)} keywords")
        
        result = await update_heatmap(request.keywords)
        
        return HeatmapUpdateResponse(
            success=True,
            new_keywords=result["new_keywords"],
            updated_keywords=result["updated_keywords"],
            decayed_keywords=result["decayed_keywords"],
            removed_keywords=result["removed_keywords"],
            affected_memories=result["affected_memories"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_heatmap endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/top_memories", response_model=TopMemoriesResponse)
async def get_top_memories(limit: int = 10):
    """
    Get the top-scored memories based on current heatmap values.
    
    Returns memories ordered by their heatmap scores (sum of matching keyword scores).
    This provides a dynamic ranking of memories based on current conversation context.
    
    Args:
        limit: Maximum number of memories to return (default: 10)
        
    Returns:
        List of memories with their heatmap scores
    """
    try:
        if limit <= 0 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        
        memories = await get_top_memories_by_heatmap(limit)
        
        return TopMemoriesResponse(memories=memories)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_top_memories endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/keyword_scores", response_model=KeywordScoresResponse)
async def get_current_keyword_scores():
    """
    Get the current keyword scores from the heatmap.
    
    Returns all keywords currently tracked in the heatmap along with their scores.
    Useful for debugging and understanding the current conversation context.
    
    Returns:
        Dictionary mapping keywords to their current relevance scores
    """
    try:
        scores = await get_keyword_scores()
        
        return KeywordScoresResponse(scores=scores)
        
    except Exception as e:
        logger.error(f"Error in get_keyword_scores endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
