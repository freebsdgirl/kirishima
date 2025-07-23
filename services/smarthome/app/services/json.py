from app.services.device import _list_devices
from app.services.entity import _list_entities

from shared.models.smarthome import Device, Entity
import json


async def _populate_devices_json():
    """
    Populate the devices.json file with a list of devices and entities.
    """

    devices = await _list_devices()  # Should be a list of dicts or objects
    entities = await _list_entities()  # Should be a list of dicts or objects

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