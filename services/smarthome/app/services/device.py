from app.util import get_ws_url, ha_ws_call
from typing import List, Dict
import json

async def _list_devices(filtered: bool = True) -> List[Dict]:
    """
    Retrieve all enabled devices from the Home Assistant device registry,
    returning only area_id, manufacturer, model, name, and id.

    Args:
        filtered (bool, optional): If True, filters devices by the configured label 
        and excludes disabled devices. Defaults to False.

    Returns:
        List[Dict]: A list of device dictionaries with selected fields.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    # Get all devices
    msg = {"id": 2, "type": "config/device_registry/list"}
    resp = await ha_ws_call(msg, ws_url, token)
    devices = resp.get('result', [])
    
    if filtered:
        ha_label = ha_config.get('label', None)
        if not ha_label:
            raise ValueError("No label specified in Home Assistant config.")
        devices = [
            d for d in devices
            if d.get('labels') and ha_label in d['labels'] and not d.get('disabled_by')
        ]
    else:
        devices = [
            d for d in devices
            if not d.get('disabled_by')
        ]
    
    # Only return the fields we care about
    result = []
    for d in devices:
        result.append({
            "area_id": d.get("area_id"),
            "manufacturer": d.get("manufacturer"),
            "model": d.get("model"),
            "name": d.get("name_by_user") or d.get("name"),
            "id": d.get("id"),
        })
    return result


async def _get_device_entities(device_ids: list, filtered: bool = True) -> list:
    """
    Retrieve all non-disabled and non-hidden entities associated with a list of devices, and their current states.

    Args:
        device_ids (list): List of device IDs.
        filtered (bool, optional): If True, filters entities by the configured label and excludes disabled or hidden entities. Defaults to True.

    Returns:
        list: List of dicts: { device_id: <id>, entities: [ {id, state, name}, ... ] }
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    ha_label = ha_config.get('label', None)

    # Get all entities
    entity_msg = {"id": 5, "type": "config/entity_registry/list"}
    entity_resp = await ha_ws_call(entity_msg, ws_url, token)
    entities = entity_resp.get('result', [])

    # Get all states once for efficiency
    all_states_msg = {"id": 100, "type": "get_states"}
    all_states_resp = await ha_ws_call(all_states_msg, ws_url, token)
    all_states = all_states_resp.get('result', [])
    states_by_id = {s['entity_id']: s for s in all_states}

    results = []
    for device_id in device_ids:
        if filtered:
            if not ha_label:
                raise ValueError("No label specified in Home Assistant config.")
            filtered_entities = [
                e for e in entities
                if e.get('device_id') == device_id
                    and e.get('labels') and ha_label in e['labels']
                    and not e.get('disabled_by')
                    and not e.get('hidden_by')
            ]
        else:
            filtered_entities = [
                e for e in entities
                if e.get('device_id') == device_id
                    and not e.get('disabled_by')
                    and not e.get('hidden_by')
            ]
        entity_objs = []
        for e in filtered_entities:
            eid = e['entity_id']
            state = states_by_id.get(eid)
            # Prefer friendly_name from state attributes, fallback to registry name
            friendly_name = None
            if state and 'attributes' in state:
                friendly_name = state['attributes'].get('friendly_name')
            if not friendly_name:
                friendly_name = e.get("name") or e.get("original_name")
            entity_objs.append({
                "id": eid,
                "state": state["state"] if state else None,
                "name": friendly_name
            })
        # Hide device if all entities are unavailable
        if entity_objs and all(ent["state"] == "unavailable" for ent in entity_objs):
            continue
        results.append({"device_id": device_id, "entities": entity_objs})
    return results