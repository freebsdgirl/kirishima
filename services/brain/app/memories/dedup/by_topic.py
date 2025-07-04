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
logger = get_logger(f"brain.{__name__}")

import os
import httpx
import json

from app.memories.topic import get_memory_by_topic
from app.memories.list import memory_get
from app.memories.delete import memory_delete
from app.memories.patch import update_memory_db

from shared.models.openai import OpenAICompletionRequest

router = APIRouter()


@router.get("/memories/dedup/by_topic")
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

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"http://ledger:{ledger_port}/topics")
            response.raise_for_status()
            topics = response.json()

            if not topics:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No topics found in the ledger."
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"Error fetching topics from ledger: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch topics from the ledger."
            )

        # Create a mapping of topic_id to topic_name
        topic_map = {topic['id']: topic['name'] for topic in topics}

        # Ask the LLM to select what topics are similar
        prompt = """
Given the following topic names, list which topics are semantically similar.

Format the output as a JSON list of lists, where each inner list contains the topic ids of names that are similar to each other.
Do not include any formatting or additional text, just the JSON array.
"""

        completion_request = OpenAICompletionRequest(
            model="gpt-4.1",
            prompt=prompt + "\n" + str(topic_map),
            max_tokens=4096,
            temperature=0.7,
            n=1
        )

        api_port = os.getenv("API_PORT", 4200)

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
            memories = []
            for topic_id in topic_ids:
                logger.debug(f"Processing topic_id: {topic_id}")
                if topic_id not in topic_map:
                    continue
                try:
                    mems = get_memory_by_topic(topic_id)
                    memories.extend(mems)
                except HTTPException as e:
                    logger.error(f"Error fetching memories for topic {topic_id}: {str(e)}")
                    continue
            if not memories:
                logger.warning(f"No memories found for topic ids: {topic_ids}")
                continue
            # For each memory, get its id and text (using memory_get)
            memory_lines = []
            for mem in memories:
                # mem may be a dict with 'id', or just an id string
                mem_id = mem["id"] if isinstance(mem, dict) and "id" in mem else mem
                try:
                    mem_row = await memory_get(mem_id)
                    # memory_get may return a dict or a response with 'memory' key
                    mem_text = mem_row["memory"] if isinstance(mem_row, dict) and "memory" in mem_row else str(mem_row)
                    memory_lines.append(f"{mem_id}|{mem_text}")
                except Exception as e:
                    logger.error(f"Error fetching memory {mem_id}: {str(e)}")
                    continue
            # Combine all memory lines into a single string
            memory_block = "\n".join(memory_lines)

            prompt = """
Given the following memories, alter them as necessary to deduplicate them. Provide the updated text for each memory, and the ids of the memories that should be deleted.

Format the output as a JSON dictionary as follows: { 'update': {'memory_id': 'new_text'}, 'delete': ['memory_id1', 'memory_id2'] }

Do not include any formatting or additional text, just the JSON object.

"""
            
            dedup_request = OpenAICompletionRequest(
                model="gpt-4.1",
                prompt=prompt+memory_block,
                max_tokens=8192,
                temperature=0.7,
                n=1
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
                    detail=f"Invalid response format from LLM. Expected JSON array, got: {text}"
                )

            # process the updates
            status = True
            # if the update fails, don't delete any of the memories marked for deletion
            if 'update' in memory_updates and isinstance(memory_updates['update'], dict):
                for mem_id, new_text in memory_updates['update'].items():
                    try:
                        update_memory_db(mem_id, memory=new_text)
                    except HTTPException as e:
                        status = False
                        logger.error(f"Failed to update memory {mem_id}: {str(e)}")
                        continue

            if status == False:
                logger.error("Failed to update some memories. No deletions will be performed.")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update some memories. No deletions will be performed."
                )

            if 'delete' in memory_updates and isinstance(memory_updates['delete'], list):
                for mem_id in memory_updates['delete']:
                    try:
                        memory_delete(mem_id)
                    except HTTPException as e:
                        logger.error(f"Failed to delete memory {mem_id}: {str(e)}")
                        continue

            # Add the result to the final output
            result.append({
                "topic": topic_map[topic_ids[0]],  # Use the first topic name for the group
                "updated memories": memory_updates.get('update', {}),
                "deleted_memories": memory_updates.get('delete', []) 
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