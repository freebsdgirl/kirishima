from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from shared.models.openai import OpenAICompletionRequest
from shared.models.ledger import (
    AssignTopicRequest,
    UserUntaggedMessagesRequest,
    TopicRecentRequest,
    TopicMessagesRequest,
    TopicCreateRequest,
    TopicDeleteRequest
)
from shared.prompt_loader import load_prompt

from app.services.user.get_untagged_messages import _get_user_untagged_messages
from app.services.topic.get_recent import _get_recent_topics
from app.services.topic.get_messages import _get_topic_messages
from app.services.topic.create import _create_topic
from app.services.topic.assign_messages import _assign_messages_to_topic
from app.services.topic.delete import _delete_topic

import httpx
import json
import os
from datetime import datetime, timedelta

from fastapi import HTTPException, status


def _normalize_topic_window(start_time: str, end_time: str) -> tuple[str, str]:
    """
    Normalize LLM-provided topic windows so they satisfy the assignment service.

    If the LLM returns an equal or reversed window, widen it minimally to preserve
    the intended anchor timestamp instead of failing the entire scan.
    """
    parsed_times = []
    for value in (start_time, end_time):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed_times.append(datetime.strptime(value, fmt))
                break
            except ValueError:
                continue
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid timestamp format from topic scan: {value}"
            )

    start_dt, end_dt = parsed_times
    if start_dt >= end_dt:
        end_dt = start_dt + timedelta(milliseconds=1)

    return (
        start_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        end_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
    )


async def _scan_user_messages():
    """
    Scan the user's messages to identify topics.
    
    This function retrieves untagged messages for a user, processes them to identify topics,
    and assigns topic windows to the transcript. Automated memory creation is disabled;
    only the conversational agent creates memories now.
        
    Returns:
        dict: A summary of the scan process including successful and error counts.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    TIMEOUT = _config["timeout"]
    user_id = _config["user_id"]

    logger.info(f"Starting topic scan for user: {user_id}")
    topics_processed = 0



    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # we don't actually use user_id for anything other than pulling messages - this is because we haven't deprecated user_ids from the user_messages table yet.
            messages = _get_user_untagged_messages(UserUntaggedMessagesRequest(user_id=user_id))
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
        conversation_config = _config.get("conversation", {})
        turns = conversation_config["turns"]
        if len(messages) <= turns:
            logger.info(f"Only {len(messages)} untagged messages found. Skipping analysis.")
            return {"status": "ok", "message": f"Only {len(messages)} untagged messages found. Skipping analysis."}

        logger.info(f"Found {len(messages)} untagged messages.")

        # Process a reasonable batch of older messages to work through the backlog
        batch_size = conversation_config.get("batch_size", 30)
        if not isinstance(batch_size, int) or batch_size <= 0:
            logger.warning(f"Invalid conversation.batch_size={batch_size!r}; falling back to 30")
            batch_size = 30

        if len(messages) > batch_size:
            logger.info(f"Processing the oldest {batch_size} untagged messages from backlog.")
            messages = messages[:batch_size]  # Take the oldest messages first

        # Get the most recent topic for re-processing
        recent_topic = _get_recent_topics(TopicRecentRequest(limit=1))

        logger.info(f"Recent topic: {recent_topic}")

        # If we have a recent topic, we'll re-process it along with new messages
        if recent_topic:
            topic_id = recent_topic[0].id
            
            # Get messages for that topic before we delete it
            topic_messages = _get_topic_messages(TopicMessagesRequest(topic_id=topic_id))
            
            # Delete the existing topic so the message window can be reprocessed.
            # We intentionally do not delete memories here anymore; background scans
            # are no longer allowed to create or destroy memories.
            logger.info(f"Deleting topic {topic_id} for reprocessing")

            try:
                _delete_topic(TopicDeleteRequest(topic_id=topic_id))
                logger.info(f"Deleted topic {topic_id}")
            except Exception as e:
                logger.warning(f"Error deleting topic {topic_id}: {e}")
            
            # Combine the old topic messages with new untagged messages for reanalysis
            topic_messages.extend(messages)
            messages = topic_messages
            
            # Re-apply message limit after combining to avoid excessive context
            max_combined = max(batch_size + 10, 50)  # Allow a bit more context when reprocessing
            if len(messages) > max_combined:
                logger.info(f"Combined messages exceed limit, truncating to {max_combined} messages")
                messages = messages[-max_combined:]  # Keep the most recent from the combined set

        # Prepare the prompt with the conversation log
        conversation_log = "\n".join([msg.created_at + "|" + msg.role + "|" + msg.content for msg in messages])

        prompt = load_prompt("ledger", "memory", "scan")
        full_prompt = f"{prompt}\n\n{conversation_log}"
        # construct our openai request
        request = OpenAICompletionRequest(
            model="gpt-4.1",
            prompt=full_prompt,
            temperature=0.7,
            provider="openai",
            max_tokens=3000
        )
        # call the API's /v1/completions endpoint with the full prompt
        api_port = os.getenv("API_PORT", "4201")  # Default to port 4201 if not set
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
        # Process topics returned by LLM. We ignore any memory candidates because
        # automated memory creation has been retired.
        topics = analysis_result.get('topics', [])
        if not topics:
            logger.info(f"No topics found.")
            return {"status": "ok", "message": "No topics found, no action needed."}

        # Process all topics returned by the LLM (no special logic for extending vs creating)
        for topic in topics:
            topic_name = topic.get('topic')
            start_time = topic.get('start')
            end_time = topic.get('end')

            # Validate required topic fields
            if not topic_name or not start_time or not end_time:
                logger.warning(f"Invalid topic data - missing required fields: {topic}")
                continue

            try:
                start_time, end_time = _normalize_topic_window(start_time, end_time)
            except HTTPException as e:
                logger.warning(f"Skipping topic with invalid window {topic}: {e.detail}")
                continue

            logger.info(f"Processing new topic '{topic_name}' from {start_time} to {end_time}.")

            new_topic = _create_topic(TopicCreateRequest(
                name=topic_name
            ))

            logger.info(f"Created new topic {new_topic}.")
            # Update messages with the new topic ID and timestamps
            _assign_messages_to_topic(body=AssignTopicRequest(
                topic_id=new_topic,
                start=start_time,
                end=end_time
            ))
            topics_processed += 1
        logger.info(f"Completed topic scan, {topics_processed} topics processed.")
        return {"status": "ok", "message": f"Topic scan completed. {topics_processed} topics processed."}
