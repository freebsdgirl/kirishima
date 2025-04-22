from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import shared.consul
import httpx

from shared.models.contacts import Contact
from shared.models.discord import DiscordDirectMessage

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/discord/message/incoming")
async def discord_message_incoming(message: DiscordDirectMessage):
    """
    Endpoint to receive incoming messages from Discord.
    This is a placeholder and should be implemented according to your application's needs.
    """
    logger.debug(f"Received incoming message from Discord: {message.model_dump()}")
    
    # get the user id from the contacts service
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')
        
            contact_data = await client.get(
                f"http://{contacts_address}:{contacts_port}/search",
                params={"key": "discord_id", "value": str(message.author_id)}
            )
            contact_data.raise_for_status()

            logger.debug(f"found contact data: {contact_data.json()}")

        except Exception as e:
            logger.exception("Error retrieving service address for ledger:", e)

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding from ledger: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from ledger: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error when contacting ledger: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )