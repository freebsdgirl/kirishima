from app.services.area import _list_area, _list_devices_in_area
from fastapi import APIRouter

router = APIRouter()


@router.get("", response_model=list)
async def list_areas() -> list:
    """
    Retrieves a list of all areas in Home Assistant.

    Returns:
        list: A list of area names.
    """
    return await _list_area()


@router.get("/{area}/devices", response_model=list)
async def list_devices_by_area(area: str) -> list:
    """
    Retrieves a list of smart home devices in a specific area.

    Args:
        area (str): The area to filter devices by (e.g., 'living room', 'bedroom').

    Returns:
        list: A list of smart home devices in the specified area.
    """
    return await list_devices_by_area(area)