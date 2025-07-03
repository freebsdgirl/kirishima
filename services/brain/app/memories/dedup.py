"""
This module provides FastAPI endpoints for deduplicating memories in a database based on shared keywords or topics.
Endpoints:
----------
- /memories/dedup/keywords:
    Finds groups of memories that share more than a specified number of keywords in common.
    Returns a dictionary with groups of memory IDs that have more than the minimum shared keywords.
- /memories/dedup/topics:
    Identifies topics with more than one memory assigned, resolving topic IDs to topic names via the ledger service.
    Returns a list of topics with their associated memory IDs, ordered by the number of memories.
- /memories/dedup/by_topic:
    Uses an LLM to find semantically similar topics and deduplicate memories within those topics.
    For each group of similar topics, retrieves associated memories, prompts the LLM to deduplicate them, and applies updates or deletions as suggested.
    Returns a list of deduplication results per topic group, including updated and deleted memories.
Dependencies:
-------------
- FastAPI for API routing and HTTP exception handling.
- sqlite3 for database access.
- httpx for HTTP requests to external services.
- OpenAICompletionRequest for LLM-based deduplication.
- Shared logging and memory management utilities.
Raises:
-------
- HTTPException: For errors in database access, external service communication, or LLM response parsing.
"""
from fastapi import APIRouter, HTTPException, status, Query
import sqlite3
import json
from typing import List, Dict

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.memories.topic import get_memory_by_topic
from app.memories.list import memory_get
from app.memories.delete import memory_delete
from app.memories.patch import update_memory_db

router = APIRouter()

@router.get("/memories/dedup/keywords", response_model=Dict[str, List[List[str]]])
def deduplicate_memories_keyword(
    min_shared_keywords: int = Query(2, description="Minimum number of shared keywords to consider memories as duplicates.")
):
    """
    Find groups of memories that share more than N keywords in common.
    Args:
        min_shared_keywords (int): Minimum number of shared keywords to consider as a group.
    Returns:
        dict: {"groups": [[memory_id1, memory_id2, ...], ...]} where each group shares >N keywords.
    """
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            # Fetch all memory ids and their tags
            cursor.execute("SELECT memory_id, tag FROM memory_tags")
            tag_rows = cursor.fetchall()
            # Build memory_id -> set of tags
            from collections import defaultdict
            mem_tags = defaultdict(set)
            for mem_id, tag in tag_rows:
                mem_tags[mem_id].add(tag.lower())
            # Find groups with >N keywords in common
            groups = []
            checked = set()
            mem_ids = list(mem_tags.keys())
            for i, mem1 in enumerate(mem_ids):
                for j in range(i+1, len(mem_ids)):
                    mem2 = mem_ids[j]
                    if (mem1, mem2) in checked or (mem2, mem1) in checked:
                        continue
                    shared = mem_tags[mem1] & mem_tags[mem2]
                    if len(shared) > min_shared_keywords:
                        # See if this group overlaps with an existing group
                        found = False
                        for group in groups:
                            if mem1 in group or mem2 in group:
                                group.update([mem1, mem2])
                                found = True
                                break
                        if not found:
                            groups.append(set([mem1, mem2]))
                    checked.add((mem1, mem2))
            # Convert sets to sorted lists for output, and sort by number of shared keywords (descending)
            # We'll use the first two memories in each group to compute the shared keyword count
            def shared_count(group):
                if len(group) < 2:
                    return 0
                # Compute max shared keywords between any two in the group
                group_list = list(group)
                max_shared = 0
                for i in range(len(group_list)):
                    for j in range(i+1, len(group_list)):
                        shared = mem_tags[group_list[i]] & mem_tags[group_list[j]]
                        if len(shared) > max_shared:
                            max_shared = len(shared)
                return max_shared
            result = [sorted(list(g)) for g in groups if len(g) > 1]
            result.sort(key=shared_count, reverse=True)
        return {"groups": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding duplicate memories: {str(e)}")

@router.get("/memories/dedup/topics", response_model=List[dict])
def deduplicate_memories_topic():
    """
    Find topics with more than one memory assigned, resolving topic_id to topic name via the ledger service.
    Returns:
        list: [{"topic": topic_name, "memories": [memory_id, ...]}, ...], ordered by number of memories descending.
    """
    import os
    import httpx
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            # Get all memory_id, topic_id pairs
            cursor.execute("SELECT memory_id, topic_id FROM memory_topics")
            topic_rows = cursor.fetchall()
            from collections import defaultdict
            topic_map = defaultdict(list)
            for mem_id, topic_id in topic_rows:
                if topic_id:
                    topic_map[topic_id].append(mem_id)
            # Only keep topics with more than one memory
            topic_map = {tid: mids for tid, mids in topic_map.items() if len(mids) > 1}
            # Sort by number of memories descending
            sorted_topics = sorted(topic_map.items(), key=lambda x: len(x[1]), reverse=True)
            # Resolve topic_ids to names (batch if possible, else one by one)
            result = []
            async def get_topic_name(topic_id):
                url = f"http://ledger:{ledger_port}/topics/id/{topic_id}"
                async with httpx.AsyncClient() as client:
                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        data = resp.json()
                        return data.get("name", topic_id)
                    except Exception:
                        return topic_id
            import asyncio
            async def build_result():
                for topic_id, mem_ids in sorted_topics:
                    topic_name = await get_topic_name(topic_id)
                    result.append({"topic": topic_name, "memories": mem_ids})
            asyncio.run(build_result())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding duplicate topics: {str(e)}")


# query ledger for the list of topic ids and names, then prompt the LLM to deduplicate memories based on topic
@router.get("/memories/dedup/by_topic")
async def deduplicate_memories_by_topic():
    """
    Find groups of memories that share the same topic.
    Returns:
        list: [{"topic": topic_name, "memories": [memory_id, ...]}, ...], ordered by number of memories descending.
    """
    import os
    import httpx
    ledger_port = os.getenv("LEDGER_PORT", 4203)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://ledger:{ledger_port}/topics")
        response.raise_for_status()
        topics = response.json()
    
    if not topics:
        return []

    # Create a mapping of topic_id to topic_name
    topic_map = {topic['id']: topic['name'] for topic in topics}

    # Now query the memories by topic
    result = []

    import os
    ledger_port = os.getenv("LEDGER_PORT", 4203)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://ledger:{ledger_port}/topics")
        response.raise_for_status()
        topics = response.json()
    if not topics:
        return []
    
    # Create a mapping of topic_id to topic_name
    topic_map = {topic['id']: topic['name'] for topic in topics}

    # Now ask the LLM to select what topics are similar
    from shared.models.openai import OpenAICompletionRequest

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
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"http://api:{api_port}/v1/completions", json=completion_request.model_dump())
        response.raise_for_status()
        completion_response = response.json()

        completion_text = completion_response['choices'][0]['content'].strip()

        # Parse the completion text as JSON
        import json
        try:
            similar_topics = json.loads(completion_text)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid response format from LLM. Expected JSON array."
            )

        # now we have a list of lists of topic ids that are similar.
        # pull the memories for each topic id and ask the LLM to deduplicate them
        for topic_ids in similar_topics:
            if not isinstance(topic_ids, list) or len(topic_ids) < 2:
                continue
            # pull the memories for each topic id
            memories = []
            for topic_id in topic_ids:
                if topic_id not in topic_map:
                    continue
                try:
                    mems = get_memory_by_topic(topic_id)
                    memories.extend(mems)
                except HTTPException as e:
                    # If a topic is not found, we can skip it or log it
                    continue
            if not memories:
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
                    # If memory_get fails, skip this memory
                    continue
            # Combine all memory lines into a single string
            memory_block = "\n".join(memory_lines)
            # Now you can use memory_block in your OpenAICompletionRequest prompt
            # ... (user will provide the prompt and API call logic) ...

            prompt = """
Given the following memories, alter them as necessary to deduplicate them. Provide the updated text for each memory, and the ids of the memories that should be deleted.

Format the output as a JSON dictionary as follows: { 'update': {'memory_id': 'new_text'}, 'delete': ['memory_id1', 'memory_id2'] }

Do not include any formatting or additional text, just the JSON object.

"""+memory_block
            
            dedup_request = OpenAICompletionRequest(
                model="gpt-4.1",
                prompt=prompt,
                max_tokens=4096,
                temperature=0.7,
                n=1
            )
            response = await client.post(f"http://api:{api_port}/v1/completions", json=dedup_request.model_dump())
            response.raise_for_status()
            data = response.json()

            text = data['choices'][0]['content'].strip()

            # Parse the completion text as JSON
            import json
            try:
                memory_updates = json.loads(text)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid response format from LLM. Expected JSON array."
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
                raise HTTPException(
                    status_code=500,
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

    return result