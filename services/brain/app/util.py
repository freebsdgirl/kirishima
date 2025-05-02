"""
Utility functions for interacting with the contacts service and other internal services.
This module provides asynchronous functions to:
- Retrieve the admin user ID from the contacts service.
- Retrieve a user's alias from the contacts service.
- Sanitize message content by removing HTML details tags.
- Post data to a specified service endpoint using Consul service discovery.
Functions:
    get_admin_user_id(): Asynchronously retrieves the admin user ID from the contacts service.
    get_user_alias(user_id): Asynchronously retrieves the alias for a given user ID from the contacts service.
    sanitize_messages(messages): Removes HTML details tags and strips whitespace from message content.
    post_to_service(service_name, endpoint, payload, error_prefix, timeout=60): Asynchronously sends a POST request to a service endpoint discovered via Consul.
    HTTPException: For HTTP and connection errors when communicating with services.
    ValueError: If required data is not found in the contacts service responses.

"""

from shared.config import TIMEOUT

import shared.consul

from shared.models.contacts import Contact

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import re

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
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
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
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
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


def sanitize_messages(messages):
    """
    Sanitizes a list of messages by removing HTML details tags and stripping whitespace.
    
    Args:
        messages (list): A list of message dictionaries to sanitize.
    
    Returns:
        list: The sanitized list of messages with details tags removed and whitespace stripped.
    
    Logs an error for any non-dictionary messages encountered during processing.
    """
    for message in messages:
        if isinstance(message, dict):
            content = message.get('content', '')
            content = re.sub(r'<details>.*?</details>', '', content, flags=re.DOTALL)
            content = content.strip()
            message['content'] = content
        else:
            logger.error(f"Expected message to be a dict, but got {type(message)}")
    return messages


async def post_to_service(service_name, endpoint, payload, error_prefix, timeout=60):
    """
    Sends a POST request to a specified service endpoint using Consul service discovery.
    
    Args:
        service_name (str): Name of the target service.
        endpoint (str): API endpoint path to call.
        payload (dict): JSON payload to send with the request.
        error_prefix (str): Prefix for error logging and exception messages.
        timeout (int, optional): Request timeout in seconds. Defaults to 60.
    
    Returns:
        httpx.Response: The response from the service.
    
    Raises:
        HTTPException: If service is unavailable, connection fails, or HTTP error occurs.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        address, port = shared.consul.get_service_address(service_name)
        if not address or not port:
            logger.error(f"{service_name.capitalize()} service address or port is not available.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{service_name.capitalize()} service is unavailable."
            )

        try:
            response = await client.post(f"http://{address}:{port}{endpoint}", json=payload)
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from {service_name} service: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"{error_prefix}: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to {service_name} service: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to {service_name} service: {req_err}"
            )

        except Exception as e:
            logger.error(f"Unexpected error while posting to {service_name} service: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while posting to {service_name} service."
            )