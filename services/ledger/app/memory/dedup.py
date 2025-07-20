"""
This module provides an API endpoint for deduplicating memories grouped by semantically similar topics using a Large Language Model (LLM).
Functions:
    deduplicate_memories_by_topic():
        Asynchronously deduplicates memories by:
            1. Fetching all topics from the ledger service.
            2. Using an LLM to group semantically similar topics.
            3. For each group:
                a. Retrieving all associated memories.
                b. Using an LLM to deduplicate the memories, suggesting updates and deletions.
                c. Applying the updates and deletions to the memory database.
            4. Returning a summary of the deduplication process for each group.
"""
from fastapi import APIRouter, HTTPException, status

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import os
import httpx
import json

from app.topic.get_all_topics import _get_all_topics
from app.memory.get_by_topic import _get_memory_by_topic
from app.memory.get import _get_memory
from app.memory.delete import _memory_delete
from app.memory.patch import _memory_patch

from shared.models.openai import OpenAICompletionRequest
from shared.models.ledger import MemoryEntry
from shared.prompt_loader import load_prompt

router = APIRouter()


@router.get("/memories/_dedup")
async def deduplicate_memories_by_topic():
    """
    Asynchronously deduplicates memories grouped by semantically similar topics using an LLM.
    This function performs the following steps:
    1. Fetches all topics from the ledger service.
    2. Uses an LLM to determine which topics are semantically similar, grouping them by topic IDs.
    3. For each group of similar topics:
        a. Retrieves all associated memories.
        b. Uses an LLM to deduplicate the memories, suggesting updates and deletions.
        c. Applies the updates and deletions to the memory database.
    4. Returns a summary of the deduplication process for each group.
    Raises:
        HTTPException: If topics cannot be fetched, if the LLM response is invalid, or if memory updates/deletions fail.
    Returns:
        list: A list of dictionaries, each containing:
            - "topic": The name of the topic group.
            - "updated memories": A dictionary mapping memory IDs to their updated text.
            - "deleted_memories": A list of memory IDs that were deleted.
    """
    ledger_port = os.getenv("LEDGER_PORT", 4203)

    result = []

    # Use helper function instead of HTTP endpoint
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

    # Ask the LLM to select what topics are similar
    prompt = load_prompt("ledger", "memory", "dedup_topic_similarity", topic_map=str(topic_map))

    completion_request = OpenAICompletionRequest(
        model="gpt-4.1",
        messages=[
            {"role": "user", "content": prompt}
        ]
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

        # pull the memories for each topic id and ask the LLM to deduplicate them
        for topic_ids in similar_topics:
            if not isinstance(topic_ids, list) or len(topic_ids) < 2:
                continue
            # pull the memories for each topic id
            memory_ids = []
            for topic_id in topic_ids:
                logger.debug(f"Processing topic_id: {topic_id}")
                if topic_id not in topic_map:
                    continue
                try:
                    mems = _get_memory_by_topic(topic_id)
                    memory_ids.extend(mems)
                except HTTPException as e:
                    logger.error(f"Error fetching memories for topic {topic_id}: {str(e)}")
                    continue
            
            if not memory_ids:
                logger.warning(f"No memories found for topic ids: {topic_ids}")
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
                logger.warning(f"No valid memories retrieved for topic ids: {topic_ids}")
                continue
            # Combine all memory lines into a single string
            memory_block = "\n".join(memory_lines)

            prompt = load_prompt("ledger", "memory", "dedup_memories", memory_block=memory_block)
            
            dedup_request = OpenAICompletionRequest(
                model="gpt-4.1",
                messages=[
                    {"role": "user", "content": prompt}
                ]
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
                continue  # Skip deletion for this topic group, but continue with other groups

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
                "topic": topic_map[topic_ids[0]],  # Use the first topic name for the group
                "updated_memories": updated_memories,
                "deleted_memories": deleted_memories
            })

    if not result:
        logger.warning("No similar topics found or no memories to deduplicate.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No similar topics found or no memories to deduplicate."
        )
    
    logger.info(f"Deduplication completed for {len(result)} topic groups.")
    logger.debug(f"Deduplication result: {result}")
    return result