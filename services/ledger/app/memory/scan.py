"""
This module provides functionality to scan user messages, identify conversational topics, and extract relevant memories using a language model (LLM). It is designed to process untagged messages, detect major conversational shifts, consolidate subtopics, and save important information as categorized memories for future reference.
Key Features:
- Retrieves untagged user messages and analyzes them for topic shifts.
- Uses an LLM to identify topics and extract memories, including keywords and categories.
- Updates message topics and saves extracted memories to the memory service.
- Assigns memories to their respective topics.
- Provides an API endpoint for scheduled scanning and extraction.
Functions:
- _scan_user_messages(user_id: str): Asynchronously scans messages for a given user, identifies topics and memories, and updates the database accordingly.
- scan(): FastAPI endpoint to trigger the scanning process, intended for periodic execution.
- HTTPException: If there are issues retrieving messages, processing LLM responses, or updating the database.

Example scheduler job:

import httpx

request = {
    "external_url": "http://ledger:4203/memories/scan",
    "trigger": "interval",
    "interval_minutes": 30,
    "metadata": {}
}

response = httpx.post("http://127.0.0.1:4201/jobs", json=request)
"""

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from shared.models.openai import OpenAICompletionRequest
from shared.models.ledger import MemoryEntry, AssignTopicRequest
from shared.prompt_loader import load_prompt

from app.user.get import _get_user_untagged_messages
from app.memory.create import _memory_add
from app.memory.assign_topic_to_memory import _memory_assign_topic
from app.topic.get_recent_topics import _get_recent_topics
from app.topic.get_messages_by_topic import _get_topic_messages
from app.topic.create import _create_topic
from app.topic.update import _assign_messages_to_topic
# Removed broken import - topic_dedup_utils was assistant-generated and deleted

import httpx
import json
import os

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]
user_id = _config["user_id"]


async def _scan_user_messages(user_id: str):
    """
    Scan the user's messages to identify topics and memories.
    
    This function retrieves untagged messages for a user, processes them to identify topics,
    and extracts relevant memories using an LLM.
    
    Args:
        user_id (str): The ID of the user whose messages are to be scanned.
    
    Returns:
        dict: A summary of the scan process including successful and error counts.
    """
    logger.info(f"Starting scan for user: {user_id}")
    memory_count = 0

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # we don't actually use user_id for anything other than pulling messages - this is because we haven't deprecated user_ids from the user_messages table yet.
            messages = _get_user_untagged_messages(user_id=user_id)
            # Filter for only untagged messages
            messages = [msg for msg in messages if getattr(msg, 'topic_id', None) is None]
        except Exception as e:
            logger.error(f"Failed to retrieve untagged messages: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to retrieve untagged messages: {e}"
            )
        if not messages:
            logger.info(f"No untagged messages found.")
            return {"status": "ok", "message": "No untagged messages found."}

        # Limit the number of messages to process
        turns = _config["conversation"]["turns"]
        if len(messages) <= turns:
            logger.info(f"Only {len(messages)} untagged messages found. Skipping analysis.")
            return {"status": "ok", "message": f"Only {len(messages)} untagged messages found. Skipping analysis."}

        logger.info(f"Found {len(messages)} untagged messages.")

        if (len(messages) > 30):
            logger.info(f"Limiting to the first {turns} messages for analysis.")
            messages = messages[:turns]

        # Get the most recent topic for context
        recent_topic = _get_recent_topics(limit=1)

        logger.info(f"Recent topic: {recent_topic}")

        # if recent_topic is not empty, get the messages for that topic
        if recent_topic:
            topic_id = recent_topic[0]['id']
            topic_messages = []

            # Get messages for that topic
            topic_messages = _get_topic_messages(topic_id)

            # Append current messages to the topic messages
            topic_messages.extend(messages)
            messages = topic_messages

        # Prepare the prompt with the conversation log
        conversation_log = "\n".join([msg.created_at + "|" + msg.role + "|" + msg.content for msg in messages])

        prompt = load_prompt("ledger", "memory", "scan")
        full_prompt = f"{prompt}\n\n{conversation_log}"
        # construct our openai request
        request = OpenAICompletionRequest(
            model="gpt-4.1",
            prompt=full_prompt,
            temperature=0.7,
            provider="openai"
        )
        # call the API's /v1/completions endpoint with the full prompt
        api_port = os.getenv("API_PORT")
        try:
            response = await client.post(
                f"http://api:{api_port}/v1/completions",
                json=request.model_dump()
            )
            response.raise_for_status()
            analysis_result = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get LLM response: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to get LLM response: {e}"
            )
        # convert the assistant's response to json
        try:
            analysis_result = json.loads(analysis_result['choices'][0]['content'])
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to parse LLM response: {e}"
            )

        # Validate LLM response structure
        if not isinstance(analysis_result, dict) or 'topics' not in analysis_result:
            logger.error(f"Invalid LLM response structure: missing 'topics' field")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Invalid LLM response structure"
            )

        logger.info(f"Analysis result: {analysis_result}")
        # Process topics and memories
        topics = analysis_result.get('topics', [])
        if not topics:
            logger.info(f"No topics found.")
            return {"status": "ok", "message": "No topics found, no action needed."}

        # Enhanced topic extension logic with better deduplication
        recent_topics = _get_recent_topics(limit=10)  # Get more recent topics for better matching
        recent_topic_id = None
        
        if recent_topics and len(topics) > 0:
            first_topic = topics[0]
            first_topic_name = first_topic.get('topic', '')
            
            # Simple check for exact name match with recent topics
            recent_topic_id = None
            for rt in recent_topics:
                if rt['name'].lower() == first_topic_name.lower():
                    recent_topic_id = rt['id']
                    break
            
            if recent_topic_id:
                logger.info(f"Extending existing topic '{recent_topic_id}' instead of creating new topic '{first_topic_name}'")
                # Remove the first topic from processing since we're extending existing
                topics = topics[1:]
                
                # Assign the new messages to the existing topic
                first_topic_start = first_topic.get('start')
                first_topic_end = first_topic.get('end')
                if first_topic_start and first_topic_end:
                    _assign_messages_to_topic(body=AssignTopicRequest(
                        topic_id=recent_topic_id,
                        start=first_topic_start,
                        end=first_topic_end
                    ))
                
                # Process memories for the extended topic
                memories = first_topic.get('memories', [])
                for memory in memories:
                    memory_text = memory.get('memory')
                    keywords = memory.get('keywords', [])
                    category = memory.get('category')

                    if not memory_text or not keywords or not category:
                        logger.warning(f"Invalid memory data: {memory}")
                        continue

                    logger.info(f"Adding memory to existing topic: {memory_text}")

                    try:
                        memory_obj = MemoryEntry(
                            memory=memory_text,
                            keywords=keywords,
                            category=category
                        )
                        result = _memory_add(memory_obj)
                        if result['status'] != 'memory created':
                            logger.error(f"Failed to add memory: {result.get('error', 'Unknown error')}")
                            continue
                        
                        memory_count += 1
                        
                        # Assign memory to existing topic
                        _memory_assign_topic(result['id'], recent_topic_id)
                    except Exception as e:
                        logger.error(f"Error adding memory to existing topic: {e}")
                        continue

        # Process remaining topics (new conversation shifts)
        for topic in topics:
            topic_name = topic.get('topic')
            start_time = topic.get('start')
            end_time = topic.get('end')
            memories = topic.get('memories', [])

            # Validate required topic fields
            if not topic_name or not start_time or not end_time:
                logger.warning(f"Invalid topic data - missing required fields: {topic}")
                continue

            logger.info(f"Processing new topic '{topic_name}' from {start_time} to {end_time} with {len(memories)} memories.")

            # Check if we should merge with any existing topic before creating new one
            # Simple exact name match for now - sophisticated dedup happens in dedup_topic_based
            existing_topic_id = None
            all_topics = _get_recent_topics(user_id, days=30)  # Check broader range
            for existing_topic in all_topics:
                if existing_topic['name'].lower() == topic_name.lower():
                    existing_topic_id = existing_topic['id']
                    break
            
            if existing_topic_id:
                logger.info(f"Merging with existing similar topic: {existing_topic_id}")
                new_topic = existing_topic_id
            else:
                new_topic = _create_topic(name=topic_name)
                logger.info(f"Created new topic {new_topic}.")

            # Update messages with the topic ID and timestamps
            _assign_messages_to_topic(body=AssignTopicRequest(
                topic_id=new_topic,
                start=start_time,
                end=end_time
            ))

            # Add memories to the memory service
            for memory in memories:
                memory_text = memory.get('memory')
                keywords = memory.get('keywords', [])
                category = memory.get('category')

                # Validate memory fields
                if not memory_text or not keywords or not category:
                    logger.warning(f"Invalid memory data - missing required fields: {memory}")
                    continue
                
                # Validate keywords is a list
                if not isinstance(keywords, list):
                    logger.warning(f"Invalid keywords format (not a list): {keywords}")
                    continue
                
                # Validate category is in allowed list
                allowed_categories = ['Health', 'Career', 'Family', 'Personal', 'Technical Projects', 'Social', 'Finance', 'Self-care', 'Environment', 'Hobbies', 'Philosophy']
                if category not in allowed_categories:
                    logger.warning(f"Invalid category '{category}', must be one of: {allowed_categories}")
                    continue

                logger.info(f"Adding memory: {memory_text} with keywords {keywords} and category {category}")

                try:
                    memory_obj = MemoryEntry(
                        memory=memory_text,
                        keywords=keywords,
                        category=category
                    )
                    result = _memory_add(memory_obj)
                    if result['status'] != 'memory created':
                        logger.error(f"Failed to add memory: {result.get('error', 'Unknown error')}")
                        continue
                    
                    memory_count += 1

                    # assign the memory to the topic
                    _memory_assign_topic(result['id'], new_topic)
                    
                except Exception as e:
                    logger.error(f"Error adding memory: {e}")
                    continue
        logger.info(f"Completed processing, {memory_count} memories added.")
        return {"status": "ok", "message": f"Scan completed. {memory_count} memories added."}


@router.post("/memories/_scan", status_code=status.HTTP_200_OK)
async def scan() -> dict:
    """
    Scan user messages to identify topics and extract memories.
    
    This endpoint is designed to be called periodically by a scheduler.
    It processes each user's untagged messages, identifies conversational shifts,
    and extracts relevant memories using an LLM.
    
    Returns:
        dict: A summary of the scan process including successful and error counts.
    
    Raises:
        HTTPException: If there are issues retrieving messages or processing the LLM response.
    """
    try:
        result = await _scan_user_messages(user_id)
        return result
    except HTTPException as e:
        logger.error(f"Scan failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during scan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during scan: {e}"
        )
