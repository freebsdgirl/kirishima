"""
This module provides asynchronous utility functions for interacting with the contacts service
using Discord user information. It allows for fetching, creating, and updating contact records
based on Discord user IDs or Discord User objects.
Functions:
    - get_id_from_user(user): Retrieves the contact ID associated with a given Discord user.
    - get_contact_from_discord_id(discord_id): Fetches a Contact object from the contacts service using a Discord user ID.
    - get_contact_from_user_id(user_id): Fetches a Contact object from the contacts service using a user ID.
    - create_contact_from_discord_user(user): Creates a new Contact in the contacts service from a Discord User object.
    - update_contact_from_discord(user, contact_id): Updates an existing Contact's Discord information in the contacts service.
All functions handle network and parsing errors gracefully, logging relevant error messages and returning None on failure.
"""
from shared.models.contacts import Contact

from typing import Dict, Any, Optional
import httpx
import os

from discord import User

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")


async def get_id_from_user(user):
    contact = await get_contact_from_discord_id(user.id)
    return contact.id if contact else None


async def get_contact_from_discord_id(discord_id: int) -> Contact:
    """
    Fetches a Contact object from the contacts service using a Discord user ID.

    Args:
        discord_id (int): The Discord user ID to search for.

    Returns:
        Contact or None: Returns a Contact instance if found, None if not found or on error.

    Logs:
        - Debug message when resolving the Discord ID.
        - Error messages for network issues, invalid JSON, parsing failures, or unexpected status codes.

    Raises:
        None: All exceptions are handled internally and logged.
    """
    logger.debug(f"resolving discord id: {discord_id}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            contacts_port = os.getenv("CONTACTS_PORT", 4202)

            response = await client.get(
                url=f"http://contacts:{contacts_port}/search",
                params={
                    "key": "discord_id",
                    "value": str(discord_id)
                }
            )

        except httpx.RequestError as err:
            logger.error(f"Network error while requesting contacts: {err}")
            return

        if response.status_code == 200:
            try:
                data = response.json()
                return Contact(**data)
            except ValueError:
                logger.error(f"Received invalid JSON: {data}")
                return
            except Exception as e:
                logger.error(f"Failed to parse Contact: {e}")
                return

        elif response.status_code == 404:
            return None

        else:
            logger.error(f"Error fetching contact [{response.status_code}]: {response.text}")

    return None


async def get_contact_from_user_id(user_id: str):
    """
    Fetches a contact by user ID from the contacts service.

    Args:
        user_id (str): The unique identifier of the user whose contact information is to be retrieved.

    Returns:
        Contact: An instance of the Contact class if the user is found.
        None: If the user is not found (HTTP 404) or if an error occurs.
        
    Raises:
        None explicitly. Logs errors and returns None on failure.

    Logs:
        - Debug message when resolving user ID.
        - Error messages for network issues or unexpected HTTP responses.
        - Prints a message if the response contains invalid JSON.
    """
    logger.debug(f"resolving user id: {user_id}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            contacts_port = os.getenv("CONTACTS_PORT", 4202)

            response = await client.get(f"http://contacts:{contacts_port}/contact/{user_id}")

        except httpx.RequestError as err:
            logger.error(f"Network error while requesting contacts: {err}")
            return

        if response.status_code == 200:
            try:
                data: Dict[str, Any] = response.json()
                return Contact(**data)
            except ValueError:
                print("Received invalid JSON")
                return

        elif response.status_code == 404:
            return None

        else:
            logger.error(f"Error fetching contact [{response.status_code}]: {response.text}")


async def create_contact_from_discord_user(user: User) -> Optional[Contact]:
    """
    Asynchronously creates a Contact object from a given Discord User.
    This function sends a POST request to the contacts service to create a new contact
    using information extracted from the provided Discord User object. The contact is
    created with the user's display name and Discord ID as fields.
    Args:
        user (User): The Discord User object from which to create the contact.
    Returns:
        Optional[Contact]: The created Contact object if successful, otherwise None.
    Logs:
        - Network errors during the HTTP request.
        - HTTP errors returned by the contacts service.
        - Errors encountered while parsing the response.
    """
    payload = {
        "aliases": [str(user)],
        "fields": [
            {"key": "discord",    "value": str(user)},
            {"key": "discord_id", "value": str(user.id)},
        ],
        "notes": None
    }

    async with httpx.AsyncClient() as client:
        try:
            contacts_port = os.getenv("CONTACTS_PORT", 4202)
            
            resp = await client.post(f"http://contacts:{contacts_port}/contact", json=payload, timeout=5.0)
            resp.raise_for_status()
    
        except httpx.RequestError as exc:
            logger.error(f"Network error while creating contact: {exc}")
            return None

        except httpx.HTTPStatusError as exc:
            logger.error(f"Failed to create contact [{exc.response.status_code}]: {exc.response.text}")
            return None

    try:
        data = resp.json()
        contact = Contact(**data)
        return contact

    except Exception as exc:
        logger.error(f"Failed to parse contact response: {exc}")
        return None


async def update_contact_from_discord(user: User, contact_id: str) -> Optional[Contact]:
    """
    Asynchronously updates a contact's Discord information in the contacts service.

    Args:
        user (User): The Discord user whose information will be used to update the contact.
        contact_id (str): The unique identifier of the contact to update.

    Returns:
        Optional[Contact]: The updated Contact object if the update is successful, or None if the contact is not found,
        a network error occurs, or the response cannot be parsed.

    Raises:
        This function does not raise exceptions; errors are logged and None is returned on failure.
    """

    payload = {
        "fields": [
            {"key": "discord",    "value": str(user)},
            {"key": "discord_id", "value": str(user.id)},
        ]
    }

    # --- Step 3: send PATCH ---
    async with httpx.AsyncClient() as client:
        try:
            contacts_port = os.getenv("CONTACTS_PORT", 4202)

            patch_resp = await client.patch(
                f"http://contacts:{contacts_port}/contact/{contact_id}",
                json=payload,
                timeout=5.0
            )
            if patch_resp.status_code == 404:
                print(f"Contact {contact_id} not found for update")
                return None
            patch_resp.raise_for_status()
        except httpx.RequestError as exc:
            print(f"Network error updating contact: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            print(f"Error updating contact [{exc.response.status_code}]: {exc.response.text}")
            return None

    # --- Step 4: parse and return ---
    try:
        updated = patch_resp.json()
        return Contact(**updated)

    except Exception as exc:
        print(f"Error parsing updated contact: {exc}")
        return None
