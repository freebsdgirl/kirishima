from app.services.json import _populate_devices_json

from fastapi import APIRouter

router = APIRouter()


@router.get("/populate-devices-json")
async def populate_devices_json():
    """
    API endpoint to populate the devices.json file with a list of devices and their entities.
    
    Returns:
        str: A message indicating the completion of the population process.
    """
    await _populate_devices_json()
    return {"message": "Devices JSON populated successfully."}