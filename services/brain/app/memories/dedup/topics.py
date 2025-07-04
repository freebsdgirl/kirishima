"""
This module provides an API endpoint for deduplicating memory topics in the memories database.
It defines a FastAPI router with a single GET endpoint `/memories/dedup/topics` that:
- Reads configuration to locate the memories database.
- Fetches all memory-topic associations from the database.
- Identifies topics linked to more than one memory.
- Resolves each topic's name by querying the ledger service.
- Returns a list of dictionaries, each containing the topic name and the list of associated memory IDs.
Modules and Libraries:
- FastAPI for API routing and HTTP exception handling.
- SQLite3 for database access.
- JSON and OS for configuration and environment management.
- HTTPX and asyncio for asynchronous HTTP requests.
- Collections for grouping memory-topic associations.
- Custom logging via `shared.log_config`.
    List[dict]: Each dictionary contains:
    HTTPException: If there is an error processing the topic map or resolving topic names.
"""

from fastapi import APIRouter, HTTPException, status
import sqlite3
import json
from typing import List
import os
import httpx
from collections import defaultdict
import asyncio

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

router = APIRouter()

@router.get("/memories/dedup/topics", response_model=List[dict])
def deduplicate_memories_topic():
    """
    Deduplicates memory topics by grouping memories that share the same topic and returns topics associated with more than one memory.
    Reads configuration to locate the memories database, fetches all memory-topic associations, and identifies topics linked to multiple memories.
    For each such topic, resolves the topic name via an HTTP request to the ledger service. Returns a list of dictionaries, each containing the topic name and the list of associated memory IDs.
    Returns:
        list[dict]: A list of dictionaries, each with keys:
            - "topic": The resolved topic name (or topic_id if resolution fails).
            - "memories": List of memory IDs associated with the topic.
    Raises:
        HTTPException: If there is an error processing the topic map.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    MEMORIES_DB = _config['db']['memories']
    
    ledger_port = os.getenv("LEDGER_PORT", 4203)
    
    with sqlite3.connect(MEMORIES_DB) as conn:
        cursor = conn.cursor()
        # Get all memory_id, topic_id pairs
        cursor.execute("SELECT memory_id, topic_id FROM memory_topics")

        topic_rows = cursor.fetchall()

        if not topic_rows:
            logger.debug("No topics found in memory_topics table.")
            return []

        topic_map = defaultdict(list)

        for mem_id, topic_id in topic_rows:
            if topic_id:
                topic_map[topic_id].append(mem_id)

        try:
            # Only keep topics with more than one memory
            topic_map = {tid: mids for tid, mids in topic_map.items() if len(mids) > 1}
        except Exception as e:
            logger.error(f"Error processing topic map: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing topics")

        if not topic_map:
            return []

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
                    logger.error(f"Error fetching topic {topic_id} from ledger: {url}")
                    return topic_id

        
        async def build_result():
            for topic_id, mem_ids in sorted_topics:
                try:
                    topic_name = await get_topic_name(topic_id)
                    result.append({"topic": topic_name, "memories": mem_ids})
                except Exception as e:
                    logger.error(f"Error fetching topic name for {topic_id}: {e}")
                    result.append({"topic": topic_id, "memories": mem_ids})

        asyncio.run(build_result())

    return result