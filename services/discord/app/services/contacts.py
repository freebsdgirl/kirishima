"""
Contacts service for Discord integration.
This module provides functionality for interacting with the contacts service
using Discord user information.
"""
from shared.models.contacts import Contact
from shared.log_config import get_logger

from typing import Dict, Any, Optional
import httpx
import os
from discord import User

logger = get_logger(f"discord.{__name__}")


class ContactsService:
    """Service for managing contact resolution and operations."""
    
    def __init__(self):
        self.timeout = 60
        self.contacts_port = os.getenv('CONTACTS_PORT', 4205)
    
    async def get_id_from_user(self, user: User) -> Optional[str]:
        """
        Retrieve the contact ID associated with a given Discord user.
        
        Args:
            user (User): Discord user object
            
        Returns:
            Optional[str]: Contact ID if found, None otherwise
        """
        contact = await self.get_contact_from_discord_id(user.id)
        return contact.get("id") if contact else None

    async def get_contact_from_discord_id(self, discord_id: int) -> Optional[Contact]:
        """
        Fetch a Contact object from the contacts service using a Discord user ID.

        Args:
            discord_id (int): The Discord user ID to search for.

        Returns:
            Optional[Contact]: Returns a Contact instance if found, None if not found or on error.
        """
        logger.debug(f"Resolving discord id: {discord_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"http://contacts:{self.contacts_port}/search",
                    params={"key": "discord_id", "value": discord_id}
                )
                
                if response.status_code == 200:
                    contacts_data = response.json()
                    if contacts_data:
                        return contacts_data
                    else:
                        logger.warning(f"No contact found for Discord ID: {discord_id}")
                        return None
                else:
                    logger.error(f"Failed to resolve Discord ID {discord_id}: {response.status_code} {response.text}")
                    return None
                    
            except httpx.RequestError as e:
                logger.error(f"Network error when contacting contacts service: {e}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error resolving Discord ID {discord_id}")
                return None

    async def get_contact_from_user_id(self, user_id: str) -> Optional[Contact]:
        """
        Fetch a Contact object from the contacts service using a user ID.

        Args:
            user_id (str): The user ID to search for.

        Returns:
            Optional[Contact]: Returns a Contact instance if found, None if not found or on error.
        """
        logger.debug(f"Resolving user id: {user_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"http://contacts:{self.contacts_port}/user/{user_id}")
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning(f"No contact found for user ID: {user_id}")
                    return None
                else:
                    logger.error(f"Failed to resolve user ID {user_id}: {response.status_code} {response.text}")
                    return None
                    
            except httpx.RequestError as e:
                logger.error(f"Network error when contacting contacts service: {e}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error resolving user ID {user_id}")
                return None

    async def create_contact_from_discord_user(self, user: User) -> Optional[Contact]:
        """
        Create a new Contact in the contacts service from a Discord User object.

        Args:
            user (User): The Discord User object to create a contact from.

        Returns:
            Optional[Contact]: Returns the created Contact instance, None on error.
        """
        logger.debug(f"Creating contact from Discord user: {user.name} ({user.id})")

        contact_data = {
            "name": user.display_name or user.name,
            "discord_id": str(user.id),
            "discord_username": user.name
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"http://contacts:{self.contacts_port}/contact",
                    json=contact_data
                )
                
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    logger.error(f"Failed to create contact: {response.status_code} {response.text}")
                    return None
                    
            except httpx.RequestError as e:
                logger.error(f"Network error when creating contact: {e}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error creating contact for Discord user {user.id}")
                return None

    async def update_contact_from_discord(self, user: User, contact_id: str) -> Optional[Contact]:
        """
        Update an existing Contact's Discord information in the contacts service.

        Args:
            user (User): The Discord User object with updated information.
            contact_id (str): The ID of the contact to update.

        Returns:
            Optional[Contact]: Returns the updated Contact instance, None on error.
        """
        logger.debug(f"Updating contact {contact_id} from Discord user: {user.name} ({user.id})")

        update_data = {
            "name": user.display_name or user.name,
            "discord_id": str(user.id),
            "discord_username": user.name
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.put(
                    f"http://contacts:{self.contacts_port}/contact/{contact_id}",
                    json=update_data
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to update contact {contact_id}: {response.status_code} {response.text}")
                    return None
                    
            except httpx.RequestError as e:
                logger.error(f"Network error when updating contact: {e}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error updating contact {contact_id} for Discord user {user.id}")
                return None
