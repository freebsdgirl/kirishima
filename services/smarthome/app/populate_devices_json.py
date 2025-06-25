"""
This module provides an API endpoint to populate a JSON file with a list of smart home devices and their associated entities.

Endpoint:
    GET /populate-devices-json

Functionality:
    - Retrieves devices and entities using utility functions.
    - Associates entities with their corresponding devices.
    - Constructs Device objects, each containing its related Entity objects.
    - Serializes the list of devices (with entities) to a JSON file at '/app/app/devices.json'.

Dependencies:
    - FastAPI for API routing.
    - Shared models for Device and Entity representations.
    - Utility functions for fetching devices and entities.
    - Standard json module for file output.
"""
from fastapi import APIRouter
from shared.models.smarthome import Device, Entity
from app.util import get_devices, get_entities
import json

router = APIRouter()


@router.get("/populate-devices-json")
async def populate_devices_json():
    """
    Populate the devices.json file with a list of devices and entities.
    """

    devices = await get_devices()  # Should be a list of dicts or objects
    entities = await get_entities()  # Should be a list of dicts or objects

    # Build a mapping from device_id to list of entities
    device_entities = {}
    for entity in entities:
        device_id = entity['device_id']
        if device_id is None:
            print(f"Entity {entity['id']} has no device_id, skipping.")
        device_entities.setdefault(device_id, []).append(entity)

    # Create Device objects with their entities
    device_list = []
    for device in devices:
        device_id = device['id']
        entities_for_device = device_entities.get(device_id, [])
        device_obj = Device(
            id=device['id'],
            name=device.get('name_by_user') or device.get('name'),
            manufacturer=device.get('manufacturer'),
            model=device.get('model'),
            entities=[
                Entity(
                    id=e.get('entity_id') or e['id'],  # Prefer entity_id, fallback to id if missing
                    name=e.get('name') or e.get('original_name') or (e.get('entity_id') or e['id']),
                    device_id=e['device_id']
                ) for e in entities_for_device
            ],
            area_id=device.get('area_id')
        )
        device_list.append(device_obj)

    # Write the devices to a JSON file
    with open('/app/app/devices.json', 'w') as f:
        json.dump([device.dict() for device in device_list], f, indent=4)