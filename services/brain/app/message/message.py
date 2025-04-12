"""
This module defines an API endpoint for handling incoming messages. The endpoint processes
messages by resolving the sender's identity, buffering the message, and optionally triggering
further summarization processing.
Modules:
    - fastapi: Provides the APIRouter and HTTPException classes for defining API routes and handling errors.
    - httpx: Used for making asynchronous HTTP requests to external services.
    - logging: Used for logging errors and debugging information.
    - shared_models: Contains data models such as IncomingMessage, MessageBufferEntry, and AddMessageBufferResponse.
Routes:
    - POST /incoming: Handles incoming messages by performing the following steps:
        1. Resolves the sender's identity using the Contacts service.
        2. Creates a placeholder contact if no matching contact is found.
        3. Buffers the message using the Summarize service.
Exceptions:
    - HTTPException: Raised for various error scenarios, such as missing required fields, service unavailability,
      or failures in contact creation and message buffering.
    - A JSON response containing the resolved user ID and the buffer entry ID for the processed message.
"""

from shared.models.proxy import IncomingMessage
from shared.models.summarize import MessageBufferEntry, AddMessageBufferResponse

import shared.consul

from shared.log_config import get_logger
logger = get_logger(__name__)

import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/incoming", status_code=status.HTTP_200_OK, response_model=dict)
async def incoming_message(message: IncomingMessage) -> dict:
    """
    Handles incoming messages by resolving sender identity and buffering the message.

    Performs three key steps:
    1. Resolves the sender's identity via the Contacts service, creating a placeholder contact if needed
    2. Buffers the message in the Summarize service
    3. Returns the resolved user ID and buffer entry ID

    Args:
        message (IncomingMessage): The incoming message with platform, sender_id, text, and timestamp

    Returns:
        dict: A response containing the ingested message details, including user_id and buffer_entry_id

    Raises:
        HTTPException: For various error scenarios such as missing fields or service unavailability
    """
    # Validate required fields.
    if not message.platform or not message.sender_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: platform and sender_id must be provided."
        )

    async with httpx.AsyncClient() as client:
        logger.debug(f"Incoming message: {message} from {message.platform} with sender_id {message.sender_id}")
        # 1. Identity Resolution via Contacts search.
        try:
            contacts_response = await client.get(
                f"http://{shared.consul.contacts_address}:{shared.consul.contacts_port}/search",
                params={"key": message.platform, "value": message.sender_id}
            )
        except Exception as e:
            logger.error(f"Error contacting Contacts service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Contacts service unavailable."
            )

        if contacts_response.status_code == status.HTTP_200_OK:
            contact_data = contacts_response.json()
            resolved_user_id = contact_data.get("id")

        elif contacts_response.status_code == status.HTTP_404_NOT_FOUND:
            logger.warning(f"Contact not found for {message.sender_id} on {message.platform}, creating placeholder.")
            # Create a placeholder contact. The contact's identifier (name) is just the sender_id.
            placeholder_contact = {
                "aliases": [message.sender_id],
                "fields": [{"key": message.platform, "value": message.sender_id}],
                "notes": ""
            }

            try:
                create_response = await client.post(
                    f"http://{shared.consul.contacts_address}:{shared.consul.contacts_port}/contact",
                    json=placeholder_contact
                )

            except Exception as e:
                logger.error(f"Error creating placeholder contact: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Contacts service unavailable for contact creation."
                )

            if create_response.status_code != status.HTTP_201_CREATED:
                logger.error(f"Placeholder contact creation failed: {create_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to create placeholder contact."
                )

            resolved_user_id = create_response.json().get("id")
        else:
            logger.error(f"Contacts service error: {contacts_response.text}")

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Error with Contacts service."
            )

        # 2. Message Buffering using the Summarize service buffer.
        buffer_entry = MessageBufferEntry(
            text=message.text,
            source="User",  # Assuming messages from incoming channels are from 'User'
            user_id=resolved_user_id,
            platform=message.platform,
            timestamp=message.timestamp.isoformat()  # Convert datetime to ISO 8601 string
        )

        try:
            buffer_response = await client.post(
                f"http://{shared.consul.summarize_address}:{shared.consul.summarize_port}/buffer",
                json=buffer_entry.model_dump()
            )
    
        except Exception as e:
            logger.error(f"Buffer write failed: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write to message buffer: {str(e)}"
            )

        if buffer_response.status_code not in (status.HTTP_200_OK, status.HTTP_201_CREATED):
            logger.error(f"Buffer service returned error: {buffer_response.text}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Buffer write failed."
            )

        # Parse the buffer service response using AddMessageBufferResponse model.
        add_buffer_resp = AddMessageBufferResponse.model_validate(buffer_response.json())

        # 3. Summarization Scheduling (Optional placeholder for additional logic)
    
    return {
        "detail": "Message ingested successfully",
        "user_id": resolved_user_id,
        "buffer_entry_id": add_buffer_resp.id
    }
