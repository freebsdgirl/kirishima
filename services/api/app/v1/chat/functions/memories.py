"""
Manages memory operations for a ChromaDB-based memory system.

This module provides functions to create, delete, list, and count memories:
- create_memory(): Adds a new memory to the database
- delete_memory(): Removes a specific memory from the database
- list_memories(): Retrieves and formats all stored memories
- count_memories(): Returns the total number of memories stored

The module uses a dedicated logger to track memory-related operations and 
integrates with a ChromaDB URL for memory management. It respects a maximum 
memory count limit and handles potential errors during database interactions.
"""

import api.config

from pydantic import BaseModel

import requests
import json

from log_config import get_logger

logger = get_logger(__name__)

from api.v1.chat.functions.mode import get_mode
class MemoryRequest(BaseModel):
    """
    Pydantic model representing a memory request with details for storing a memory.

    Args:
        memory (str): The content of the memory to be stored.
        component (str): The component or 'mode' associated with the memory.
        priority (float, optional): The priority of the memory, ranging from 0 to 1.
    """
    memory: str
    component: str
    priority: float


def create_memory(input: str, priority: float) -> None:
    """
    Creates a new memory in the brain's memory system.
    
    Adds a memory with the given input text and priority. Handles both string and list inputs,
    using the first element if a list is provided. Sends a memory creation request to the brain
    and logs the result.
    
    Args:
        input (str or list): The memory content to be stored. If a list is provided, the first element is used.
        priority (float): The priority of the memory, ranging from 0 to 1.
    """
    logger.info(f"📝 Creating memory: {input}")

    # i'm not sure why this is here, precisely. but if we have a list, only process
    # the first entry as a memory. i'm leaving it here for now until i determine
    # why it's here. 
    if isinstance(input, list):
        input = input[0]
    
    mode = get_mode()
    memory_request = MemoryRequest(
        memory=input,
        component=f"proxy_{mode}",
        priority=priority
    )

    try:
        response = requests.post(api.config.BRAIN_MEMORY_BASE_URL, json=memory_request.model_dump())

        if response.status_code != 200:
            logger.error(f"🤯 ERROR contacting brain: {response.status_code} - {response.text}")
            return

        logger.debug(f"💾 Created memory:\n{input}")

    except Exception as e:
        logger.error(f"🤯 ERROR contacting brain: {str(e)}")
        return


class SearchForId(BaseModel):
    """
    Pydantic model representing the search request payload for finding a memory document by input text.
    
    Attributes:
        input (str): The text input to search for in memory documents.
    """
    input: str


# todo - delete should include mode toggle
def delete_memory(input: str) -> None: 
    """
    Deletes a memory from the brain's memory system.
    
    Searches for a memory's unique identifier using the provided input text, 
    then sends a delete request to remove the memory from the brain.
    
    Args:
        request (SearchForId): A request object containing the input text to identify the memory to delete.
    
    Returns:
        None: Returns silently on successful deletion or if an error occurs during the process.
    """
    logger.info(f"🗑️ Deleting memory: {input}")

    payload = {
        "input": input
    }

    # get the id of the memory to be deleted
    try:
        response = requests.post(f"{api.config.BRAIN_MEMORY_BASE_URL}/search/id", json=payload)
        if response.status_code != 200:
            logger.error(f"🤯 ERROR querying brain: {response.status_code} - {response.text}")
            return

        result = response.json()
        id = result.get("id")
    except Exception as e:
        logger.error(f"🤯 ERROR querying brain: {str(e)}")
        return

    # delete the id
    try:
        response = requests.delete(f"{api.config.BRAIN_MEMORY_BASE_URL}/{id}")
        if response.status_code != 200:
            logger.error(f"🤯 ERROR querying brain: {response.status_code} - {response.text}")
            return

        logger.debug(f"✅ Deleted memory:\n{input} ({id})")

    except Exception as e:
        logger.error(f"🤯 ERROR contacting brain: {str(e)}")
        return


def list_memories():
    logger.debug("📝 Listing memories.")

    try:
        # limit should probably be set from context window or in config? and it's only pulling the 100
        # oldest. gotta fix that.
        mode = get_mode()
        response = requests.get(f"{api.config.BRAIN_MEMORY_BASE_URL}?component=proxy_{mode}&limit=100")
        if response.status_code != 200:
            logger.error(f"🤯 ERROR querying brain: {response.status_code} - {response.text}")
            return ""

        results = response.json()
        logger.debug(f"🔍 ChromaDB Search Results: {json.dumps(results, indent=2, ensure_ascii=False)}")

        # Extract the 'document' from each memory object
        messages = [mem["document"] for mem in results]

        final_text = "\n".join(f"{i+1}. {line}" for i, line in enumerate(messages))

        logger.debug(f"✅ Memories Listed:\n{final_text}") 
        return f"[MEMORIES]\n{final_text}"

    except Exception as e:
        logger.error(f"❌ ERROR querying ChromaDB: {str(e)}")
        return ""

