"""
This module provides an API endpoint for reviewing conversation logs, identifying major conversational topics and extracting relevant memories for each user.

The main endpoint `/review_log` is designed to be called periodically (e.g., every 3 hours) by a scheduler. It performs the following steps:
- Retrieves the list of users from the contacts service.
- For each user, fetches untagged messages and the most recent conversation topic.
- Aggregates messages for analysis, including those from the most recent topic if available.
- Constructs a prompt and sends it to an LLM (via the API service) to identify conversational shifts (topics) and extract memories.
- For each identified topic:
    - Creates a new topic in the ledger service.
    - Assigns relevant messages to the new topic based on timestamps.
    - Adds extracted memories to the memory service, associating them with the topic.
- Handles errors gracefully and logs progress and issues throughout the process.

Returns a summary message upon completion.
"""

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.tools.memory_add import memory_add
from app.tools.memory_topic import memory_topic
from shared.models.openai import OpenAICompletionRequest

import httpx
import json
import os

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]



@router.get("/review_log", status_code=status.HTTP_200_OK)
async def review_log():
    """
    Review the log of conversations and identify topics and memories.
    This endpoint is called by the scheduler every 3 hours.
    """
    logger.info("Starting review log process...")
    # Get the list of users
    contacts_port = os.getenv("CONTACTS_PORT")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(f"http://contacts:{contacts_port}/contacts")
            response.raise_for_status()
            users = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to retrieve users: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="Failed to retrieve users.")
        except httpx.RequestError as e:
            logger.error(f"Request error while retrieving users: {e}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable while retrieving users.")

        if not users:
            logger.info("No active users found.")
            return {"message": "No active users found."}

        for user in users:
            user_id = user['id']
            logger.info(f"Processing user: {user_id}")

            # Retrieve untagged messages for the user
            ledger_port = os.getenv("LEDGER_PORT")
            try:
                response = await client.get(
                    f"http://ledger:{ledger_port}/user/{user_id}/messages/untagged"
                )
                response.raise_for_status()
                messages = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to retrieve untagged messages for user {user_id}: {e.response.status_code} - {e.response.text}")
                continue
            except httpx.RequestError as e:
                logger.error(f"Request error while retrieving untagged messages for user {user_id}: {e}")
                continue
            if not messages:
                logger.info(f"No untagged messages found for user {user_id}.")
                continue

            logger.info(f"Found {len(messages)} untagged messages for user {user_id}.")

            # Get the most recent topic for the user
            try:
                response = await client.get(
                    f"http://ledger:{ledger_port}/topics/recent",
                    params={"n": 1, "user_id": user_id}
                )
                response.raise_for_status()
                recent_topic = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to retrieve recent topic for user {user_id}: {e.response.status_code} - {e.response.text}")
                continue
            except httpx.RequestError as e:
                logger.error(f"Request error while retrieving recent topic for user {user_id}: {e}")
                continue

            logger.info(f"Recent topic for user {user_id}: {recent_topic}")

            # if recent_topic is not empty, get the messages for that topic
            if recent_topic:
                topic_id = recent_topic[0]['id']
                topic_messages = []

                try:
                    # Get messages for that topic
                    response = await client.get(
                        f"http://ledger:{ledger_port}/topics/{topic_id}/messages"
                    )
                    response.raise_for_status()
                    topic_messages = response.json()
                except httpx.HTTPStatusError as e:
                    logger.error(f"Failed to retrieve messages for topic {topic_id} for user {user_id}: {e.response.status_code} - {e.response.text}")
                    continue
                except httpx.RequestError as e:
                    logger.error(f"Request error while retrieving messages for topic {topic_id} for user {user_id}: {e}")
                    continue

                # Append current messages to the topic messages
                topic_messages.extend(messages)
                messages = topic_messages

            # Prepare the prompt with the conversation log
            conversation_log = "\n".join([msg['created_at'] + "|" + msg['role'] + "|" + msg['content'] for msg in messages])

            prompt = """
Given the following log, identify and list the major conversational shifts. 
- Do not give commentary. 
- Only list significant shifts in conversation. 
- Consolidate all subtopics into a single topic. 
- Do not list any subtopics, even if they are technical in nature.
- After each conversational shift, specify a short phrase that defines this topic.
- Treat all parts of the conversation that center around the same general theme (such as ‘AI’) as one topic, regardless of which aspects or points are discussed. Only consider it a new topic if the general theme of conversation changes to something else (such as ‘personal job search’ or ‘home routines’).
- Refer to the user as Randi and the assistant as Kirishima.

Once you have identified the conversational shifts, examine each conversation and determine if there is any data that should be saved as a memory.
- Memories should include anything that might be referenced in later conversations. 
- Do not include things the model likely already knows.
- Identify up to 4 relevant keywords for each memory. Do not use 'Randi' or 'Kirishima' as keywords. Only include keywords that will be useful for search.
- Include a category for the memory. You must choose from one of the following: Health, Career, Family, Personal, Technical Projects, Social, Finance, Self-care, Environment, Hobbies, Philosophy

Output should be in JSON matching the format: 
{ 
    "topics": [ 
        { 
            "topic": "topic name goes here", 
            "start": "beginning timestamp goes here", 
            "end": "end timestamp goes here",
            "memories:" [
                {
                    "memory": "memory 1",
                    "keywords": [ "keyword1", "keyword2", ... ],
                    "category": "Health"
                },
                ...
            ] 
        },
        ...
    ]
}
- Do not include formatting.
"""
            full_prompt = f"{prompt}\n\n{conversation_log}"

            # construct our openai request
            request = OpenAICompletionRequest(
                model="gpt-4.1",
                prompt=full_prompt,
                max_tokens=4096,
                temperature=0.7,
                provider="openai",
                n=1
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
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to get LLM response for user {user_id}: {e.response.status_code} - {e.response.text}")
                continue
            except httpx.RequestError as e:
                logger.error(f"Request error while getting LLM response for user {user_id}: {e}")
                continue

            # convert the assistant's respones to json
            try:
                analysis_result = json.loads(analysis_result['choices'][0]['content'])
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse LLM response for user {user_id}: {e}")
                continue

            logger.info(f"Analysis result for user {user_id}: {analysis_result}")
            # Process topics and memories
            topics = analysis_result.get('topics', [])
            if not topics:
                logger.info(f"No topics found for user {user_id}.")
                continue
            for topic in topics:
                topic_name = topic.get('topic')
                start_time = topic.get('start')
                end_time = topic.get('end')
                memories = topic.get('memories', [])

                logger.info(f"Processing topic '{topic_name}' for user {user_id} from {start_time} to {end_time} with {len(memories)} memories.")

                try:
                    response = await client.post(
                        f"http://ledger:{ledger_port}/topics",
                        params={"name": topic_name}
                    )
                    response.raise_for_status()
                    new_topic_id = response.json()
                except httpx.HTTPStatusError as e:
                    logger.error(f"Failed to create topic {topic_name} for user {user_id}: {e.response.status_code} - {e.response.text}")
                    continue
                except httpx.RequestError as e:
                    logger.error(f"Request error while creating topic {topic_name} for user {user_id}: {e}")
                    continue

                logger.info(f"Created new topic {new_topic_id} for user {user_id}.")
                # Update messages with the new topic ID and timestamps
                try:
                    await client.patch(
                        f"http://ledger:{ledger_port}/topics/{new_topic_id}/assign",
                        params={"start": start_time, "end": end_time}
                    )
                except httpx.HTTPStatusError as e:
                    logger.error(f"Failed to assign messages to topic {new_topic_id} for user {user_id}: {e.response.status_code} - {e.response.text}")
                    continue
                except httpx.RequestError as e:
                    logger.error(f"Request error while assigning messages to topic {new_topic_id} for user {user_id}: {e}")
                    continue

                # Add memories to the memory service
                for memory in memories:
                    memory_text = memory.get('memory')
                    keywords = memory.get('keywords', [])
                    category = memory.get('category')

                    if not memory_text or not keywords or not category:
                        logger.warning(f"Invalid memory data for user {user_id}: {memory}")
                        continue

                    logger.info(f"Adding memory for user {user_id}: {memory_text} with keywords {keywords} and category {category}")

                    try:
                        result = memory_add(memory=memory_text, keywords=keywords, category=category, priority=0.5)
                        if result['status'] != 'memory created':
                            logger.error(f"Failed to add memory for user {user_id}: {result['error']}")
                    except Exception as e:
                        logger.error(f"Error adding memory for user {user_id}: {e}")

                    # assign the memory to the topic
                    try:
                        memory_topic(result['id'], new_topic_id)
                    except httpx.HTTPStatusError as e:
                        logger.error(f"Failed to assign memory {result['id']} to topic {new_topic_id} for user {user_id}: {e.response.status_code} - {e.response.text}")
                    except httpx.RequestError as e:
                        logger.error(f"Request error while assigning memory {result['id']} to topic {new_topic_id} for user {user_id}: {e}")
            logger.info(f"Completed processing for user {user_id}.")

    return {"message": "Review log completed successfully."}