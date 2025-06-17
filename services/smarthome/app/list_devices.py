from fastapi import APIRouter

router = APIRouter()


@router.get("/devices", response_model=list)
async def list_devices(filtered: bool = True) -> list:
    """
    Retrieves a list of available smart home devices from Home Assistant.

    Returns:
        list: A list of available smart home devices/entities with the configured label.
    """
    if filtered:
        from app.util import get_filtered_entities
        return await get_filtered_entities()
    else:   
        from app.util import get_device_list
        return await get_device_list()

