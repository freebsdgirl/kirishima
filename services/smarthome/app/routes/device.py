from app.services.device import _list_devices, _get_device_entities

from fastapi import APIRouter

router = APIRouter()


@router.get("", response_model=list)
async def list_devices(filtered: bool = True) -> list:
    """
    Retrieves a list of available smart home devices from Home Assistant.

    Returns:
        list: A list of available smart home devices/entities with the configured label.
    """
    return await _list_devices(filtered=filtered)


@router.get("/{device_id}/entities", response_model=list)
async def get_device_entities(device_id: str) -> list:
    """
    Retrieves all entities associated with a specific device.

    Args:
        device_id (str): The ID of the device to retrieve entities for.

    Returns:
        dict: A dictionary containing the device's entities.
    """
    return await _get_device_entities(device_id)

