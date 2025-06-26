"""
This module provides utility functions to interact with the stickynotes microservice,
enabling creation, listing, snoozing, resolving, and checking of sticky notes for a user.

Functions:
    stickynotes(action: str, text: str = None, snooze: str = None, periodicity: str = None, id: str = None, date: str = None)
        Asynchronously interacts with the stickynotes microservice to perform actions such as create, list, snooze, and resolve sticky notes.

    check_stickynotes(user_id: str)
        Asynchronously calls the stickynotes /check endpoint to retrieve due sticky notes for a user.
        Returns a simulated tool call and tool output if there are due notes, or an empty list otherwise.
"""
import httpx
from fastapi import HTTPException
import uuid
import json


user_id = 'c63989a3-756c-4bdf-b0c2-13d01e129e02'
stickynotes_base_url = "http://stickynotes:4214"

from shared.log_config import get_logger
logger = get_logger(f"brain.tools.{__name__}")


async def stickynotes(
    action: str,
    text: str = None,
    snooze: str = None,
    periodicity: str = None,
    id: str = None,
    date: str = None  # Accept date as an optional argument
):
    """
    Tool function to interact with the stickynotes microservice.
    Returns the raw API response for each action.
    """
    async with httpx.AsyncClient() as client:
        if action == "create":
            payload = {"text": text, "user_id": user_id}
            if periodicity:
                payload["periodicity"] = periodicity
            if date:
                payload["due"] = date
            logger.debug(f"Creating sticky note with payload: {payload}")
            response = await client.post(f"{stickynotes_base_url}/create", json=payload)
        elif action == "list":
            logger.debug(f"Listing sticky notes for user_id={user_id}.")
            response = await client.get(f"{stickynotes_base_url}/list", params={"user_id": user_id})
        elif action == "snooze":
            logger.debug(f"Snoozing sticky note with id={id} for snooze time={snooze}.")
            if not id or not snooze:
                raise HTTPException(status_code=400, detail="id and snooze are required for snooze action.")
            response = await client.post(f"{stickynotes_base_url}/snooze/{id}", params={"snooze_time": snooze})
        elif action == "resolve":
            logger.debug(f"Resolving sticky note with id={id}.")
            if not id:
                raise HTTPException(status_code=400, detail="id is required for resolve action.")
            response = await client.get(f"{stickynotes_base_url}/resolve/{id}")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        response.raise_for_status()
        return response.json()



async def check_stickynotes(user_id: str):
    """
    Calls the stickynotes /check endpoint and returns a simulated tool call and tool output,
    or an empty list if there are no due stickynotes.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{stickynotes_base_url}/check", params={"user_id": user_id})
        response.raise_for_status()
        notes = response.json()
        if not notes:
            return []
        tool_call_id = str(uuid.uuid4())
        # Simulate the assistant calling the tool
        assistant_dict = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "stickynotes",
                        "arguments": f'{{"action": "check", "user_id": "{user_id}"}}'
                    }
                }
            ]
        }
        # Simulate the tool's response
        tool_dict = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(notes)
        }
        return [assistant_dict, tool_dict]