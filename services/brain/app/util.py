"""
This module provides utility functions for interacting with the contacts service,
including retrieving the admin user's unique identifier.
Functions:
    get_admin_user_id: Asynchronously retrieves the user ID of the admin user from the contacts service.
    get_user_alias: Asynchronously retrieves the alias of a user based on their unique identifier.
"""

import shared.consul

from shared.models.contacts import Contact

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
from fastapi import HTTPException, status


async def get_admin_user_id() -> str:
    """
    Retrieve the user ID for the admin user from the contacts service.
    
    Queries the contacts service to find a user with the '@ADMIN' tag and returns their user ID.
    Raises an HTTPException if there are any HTTP-related errors during the retrieval process.
    
    Returns:
        str: The unique identifier of the admin user.
    
    Raises:
        ValueError: If no admin user is found in the contacts service.
        HTTPException: If there is an error communicating with the contacts service.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')
            contact_response = await client.get(
                f"http://{contacts_address}:{contacts_port}/search",
                params={"q": "@ADMIN"}
            )
            
            contact_response.raise_for_status()
            data = contact_response.json()
            if not data.get("id"):
                logger.error("No admin user found in contacts service.")
                raise ValueError("No admin user found in contacts service.")
            return data["id"]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Error retrieving admin user ID."
            )
        
        except Exception as e:
            logger.exception("Error retrieving admin user ID from contacts service:", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while retrieving admin user ID."
            )


async def get_user_alias(user_id: str) -> str:
    """
    Retrieve the alias for a specific user from the contacts service.
    
    Queries the contacts service to find a user with the specified user ID and returns their alias.
    Raises an HTTPException if there are any HTTP-related errors during the retrieval process.
    
    Args:
        user_id (str): The unique identifier of the user whose alias is to be retrieved.
    
    Returns:
        str: The alias of the specified user.
    
    Raises:
        HTTPException: If there is an error communicating with the contacts service.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')
            contact_response = await client.get(f"http://{contacts_address}:{contacts_port}/contact/{user_id}")
            contact_response.raise_for_status()

            model = Contact.model_validate(contact_response.json())
            if not model.aliases or not isinstance(model.aliases, list) or not model.aliases[0]:
                logger.error(f"No alias found for user {user_id} in contacts service.")
                raise ValueError(f"No alias found for user {user_id} in contacts service.")

            return model.aliases[0]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Error retrieving user alias."
            )
        
        except Exception as e:
            logger.exception("Error retrieving user alias from contacts service:", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while retrieving user alias."
            )