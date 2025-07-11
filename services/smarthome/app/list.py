"""
This module defines API endpoints for listing and retrieving information about areas, devices, and entities
in a Home Assistant-based smart home system.

Routes:
    - GET /areas: Retrieves a list of all area names.
    - GET /devices: Retrieves a list of available smart home devices, optionally filtered.
    - GET /area/{area}/devices: Retrieves devices located in a specific area.
    - GET /device/{device_id}/entities: Retrieves all entities associated with a specific device.
    - GET /entities: Retrieves a list of all entities.
    - GET /entity/{entity_id}: Retrieves details for a specific entity by its ID.

Each endpoint interacts with utility functions from the `app.util` module to fetch and return the requested data.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/areas", response_model=list)
async def list_areas() -> list:
    """
    Retrieves a list of all areas in Home Assistant.

    Returns:
        list: A list of area names.
    """
    from app.util import get_area_names
    return await get_area_names()


@router.get("/devices", response_model=list)
async def list_devices(filtered: bool = True) -> list:
    """
    Retrieves a list of available smart home devices from Home Assistant.

    Returns:
        list: A list of available smart home devices/entities with the configured label.
    """
    from app.util import get_devices
    return await get_devices(filtered=filtered)


@router.get("/area/{area}/devices", response_model=list)
async def list_devices_by_area(area: str) -> list:
    """
    Retrieves a list of smart home devices in a specific area.

    Args:
        area (str): The area to filter devices by (e.g., 'living room', 'bedroom').

    Returns:
        list: A list of smart home devices in the specified area.
    """
    from app.util import get_devices_in_area
    return await get_devices_in_area(area)


@router.get("/device/{device_id}/entities", response_model=list)
async def get_device_entities(device_id: str) -> list:
    """
    Retrieves all entities associated with a specific device.

    Args:
        device_id (str): The ID of the device to retrieve entities for.

    Returns:
        dict: A dictionary containing the device's entities.
    """
    from app.util import get_entities_for_device
    return await get_entities_for_device(device_id)


@router.get("/entities", response_model=list)
async def list_entities() -> list:
    """
    Retrieves a list of all entities in Home Assistant.

    Returns:
        list: A list of entity names.
    """
    from app.util import get_entities
    return await get_entities()


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str):
    """
    Retrieves details for a specific entity by its ID.

    Args:
        entity_id (str): The ID of the entity to retrieve.
    Returns:
        dict: A dictionary containing the entity's details.
    """
    from app.util import get_states_for_entity_ids
    return await get_states_for_entity_ids([entity_id])