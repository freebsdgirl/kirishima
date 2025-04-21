import shared.consul

from shared.models.contacts import Contact

from typing import Dict, Any, Optional
import httpx

from discord import User

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")


async def get_id_from_user(user):
    contact = await get_contact_from_discord_id(user.id)
    return contact.id if contact else None


async def get_contact_from_discord_id(discord_id: int) -> Contact:
    logger.debug(f"resolving discord id: {discord_id}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')
            if not contacts_address or not contacts_port:
                logger.error("Contacts service address or port is not available.")

                raise Exception(
                    detail="Contacts service is unavailable."
                )

            response = await client.get(
                url=f"http://{contacts_address}:{contacts_port}/search",
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
    logger.debug(f"resolving user id: {user_id}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')
            if not contacts_address or not contacts_port:
                logger.error("Contacts service address or port is not available.")

                raise Exception(
                    detail="Contacts service is unavailable."
                )

            response = await client.get(f"http://{contacts_address}:{contacts_port}/contact/{user_id}")

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
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')
            if not contacts_address or not contacts_port:
                logger.error("Contacts service address or port is not available.")

                raise Exception(
                    detail="Contacts service is unavailable."
                )
            
            resp = await client.post(f"http://{contacts_address}:{contacts_port}/contact", json=payload, timeout=5.0)
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
    Patch an existing contact in the contacts service using data from a discord.py User.
    - Patches the fields "discord" and "discord_id" with the User info.
    - Returns the updated Contact model, or None on error.
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
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')
            if not contacts_address or not contacts_port:
                logger.error("Contacts service address or port is not available.")

                raise Exception(
                    detail="Contacts service is unavailable."
                )

            patch_resp = await client.patch(
                f"http://{contacts_address}:{contacts_port}/contact/{contact_id}",
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
