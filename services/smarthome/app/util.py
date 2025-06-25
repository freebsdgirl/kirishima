"""
Utility functions for interacting with Home Assistant via WebSocket API.
This module provides asynchronous helpers to:
- Connect to Home Assistant's WebSocket API.
- Retrieve and filter areas, devices, entities, and their states.
- Support filtering by custom labels and exclusion of disabled/hidden items.
- Retrieve options for entities, with support for lighting overrides.
Configuration is loaded from '/app/config/config.json' and must include Home Assistant connection details.
Functions:
    ha_ws_call(message: dict, ws_url: str, token: str) -> dict
        Send a message to Home Assistant WebSocket API and return the response.
    get_ws_url() -> str
        Construct the Home Assistant WebSocket URL from configuration.
    get_area_names() -> List[str]
    get_devices(filtered: bool = True) -> List[Dict]
        Retrieve all enabled devices, optionally filtered by label.
    get_devices_in_area(area_name: str, filtered: bool = True) -> List[Dict]
    get_entities_for_device(device_ids: list, filtered: bool = True) -> list
        Retrieve all non-disabled and non-hidden entities for a list of devices, with their current states.
    get_entities(filtered: bool = True) -> List[Dict]
        Retrieve entities from the registry, optionally filtered by label.
    get_states_for_entity_ids(entity_ids: List[str]) -> List[Dict]
        Retrieve the current states for a specific list of entity IDs.
    get_states(filtered: bool = True) -> List[Dict]
        Retrieve states from Home Assistant, optionally filtered by label.
    get_options_for_entity(entity_id: str, lighting_overrides: dict = None) -> list
        Retrieve possible options for an entity, using lighting overrides if provided.

"""
import json
import websockets
from typing import List, Dict

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


# WebSocket API helper
async def ha_ws_call(message: dict, ws_url: str, token: str) -> dict:
    async with websockets.connect(ws_url, ping_interval=None) as ws:
        # Receive auth_required
        await ws.recv()
        # Send auth
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        # Receive auth_ok
        await ws.recv()
        # Send our message
        await ws.send(json.dumps(message))
        # Wait for result
        while True:
            resp = json.loads(await ws.recv())
            if resp.get("id") == message["id"]:
                return resp


# Helper to get ws_rl
def get_ws_url() -> str:
    ha_config = _config['homeassistant']
    ha_url = ha_config['url']
    if not ha_url.startswith('ws'):
        if ha_url.startswith('http://'):
            ha_url = ha_url.replace('http://', 'ws://')
        elif ha_url.startswith('https://'):
            ha_url = ha_url.replace('https://', 'wss://')
        else:
            ha_url = f'ws://{ha_url}'
    return f"{ha_url}/api/websocket"


async def get_area_names() -> List[str]:
    """
    Retrieve all area names from the Home Assistant area registry.
    
    Returns:
        List[str]: A list of area names registered in Home Assistant.
    """
    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    msg = {"id": 1, "type": "config/area_registry/list"}
    resp = await ha_ws_call(msg, ws_url, token)
    return [area['name'] for area in resp.get('result', [])]


async def get_devices(filtered: bool = True) -> List[Dict]:
    """
    Retrieve all enabled devices from the Home Assistant device registry,
    returning only area_id, manufacturer, model, name, and id.

    Args:
        filtered (bool, optional): If True, filters devices by the configured label 
        and excludes disabled devices. Defaults to False.

    Returns:
        List[Dict]: A list of device dictionaries with selected fields.
    """
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


async def get_devices_in_area(area_name: str, filtered: bool = True) -> List[Dict]:
    """
    Retrieve all enabled devices within a specific area by area name.
    
    Args:
        area_name (str): The name of the area to retrieve devices from.
        filtered (bool, optional): If True, filters devices by the configured label.
    
    Returns:
        List[Dict]: A list of enabled device dictionaries located in the specified area.
        Returns an empty list if the area is not found.
    """
    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    
    # Get all devices
    msg = {"id": 3, "type": "config/device_registry/list"}
    resp = await ha_ws_call(msg, ws_url, token)
    devices = resp.get('result', [])
    
    # Filter devices by area name
    filtered_devices = [
        d for d in devices
        if d.get('area_id') and d.get('area_name') == area_name and not d.get('disabled_by')
    ]
    
    if filtered:
        ha_label = ha_config.get('label', None)
        if not ha_label:
            raise ValueError("No label specified in Home Assistant config.")
        
        filtered_devices = [
            d for d in filtered_devices
            if d.get('labels') and ha_label in d['labels']
        ]
    
    return filtered_devices


async def get_entities_for_device(device_ids: list, filtered: bool = True) -> list:
    """
    Retrieve all non-disabled and non-hidden entities associated with a list of devices, and their current states.

    Args:
        device_ids (list): List of device IDs.
        filtered (bool, optional): If True, filters entities by the configured label and excludes disabled or hidden entities. Defaults to True.

    Returns:
        list: List of dicts: { device_id: <id>, entities: [ {id, state, name}, ... ] }
    """
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


async def get_entities(filtered: bool = True) -> List[Dict]:
    """
    Retrieve entities from the Home Assistant entity registry, returning only
    device_id, entity_id, and name (preferring 'name', falling back to 'original_name').

    Args:
        filtered (bool, optional): If True, filters entities by the configured label 
        and excludes disabled or hidden entities. Defaults to False.

    Returns:
        List[Dict]: A list of entity dictionaries with selected fields.
    """
    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    if not token:
        raise ValueError("No token specified in Home Assistant config.")
    ha_label = ha_config.get('label', None)
    if not ha_label:
        raise ValueError("No label specified in Home Assistant config.")

    entity_msg = {"id": 6, "type": "config/entity_registry/list"}
    entity_resp = await ha_ws_call(entity_msg, ws_url, token)
    entities = entity_resp.get('result', [])

    if filtered:
        entities = [
            e for e in entities
            if e.get('labels') 
                and ha_label in e['labels']
                and not e.get('disabled_by') 
                and not e.get('hidden_by')
        ]
    # Only return the fields we care about
    result = []
    for e in entities:
        result.append({
            "device_id": e.get("device_id"),
            "entity_id": e.get("entity_id"),
            "name": e.get("name") or e.get("original_name"),
        })
    return result


async def get_states_for_entity_ids(entity_ids: List[str]) -> List[Dict]:
    """
    Retrieve the current states for a specific list of entity IDs from Home Assistant.
    
    Args:
        entity_ids (List[str]): A list of entity IDs to retrieve states for.
    
    Returns:
        List[Dict]: A list of state dictionaries for the specified entity IDs, 
        including their current attributes and values.
    """
    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    # Get all states (this includes attributes)
    msg = {"id": 100, "type": "get_states"}
    resp = await ha_ws_call(msg, ws_url, token)
    all_states = resp.get('result', [])
    # Filter for requested entity_ids
    filtered = [s for s in all_states if s.get('entity_id') in entity_ids]
    return filtered


async def get_states(filtered: bool = True) -> List[Dict]:
    """
    Retrieve states from Home Assistant, with optional filtering by label.
    
    Args:
        filtered (bool, optional): If True, filters states to only include entities 
        with the configured Home Assistant label and exclude hidden/disabled entities. 
        Defaults to False.
    
    Returns:
        List[Dict]: A list of state dictionaries for entities, optionally filtered 
        by label and visibility status.
    
    Raises:
        ValueError: If filtering is enabled and no label is specified in the configuration.
    """
    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']

    # Get all states (this includes attributes)
    msg = {"id": 101, "type": "get_states"}
    resp = await ha_ws_call(msg, ws_url, token)
    all_states = resp.get('result', [])
    
    # Filter for entities with the configured label, not hidden or disabled
    if filtered:
        ha_label = ha_config.get('label', None)
        if not ha_label:
            raise ValueError("No label specified in Home Assistant config.")

        filtered_entities = [
            s for s in all_states
            if s.get('entity_id') and 
            s.get('attributes', {}).get('labels') and 
            ha_label in s['attributes']['labels'] and 
            not s.get('attributes', {}).get('hidden_by') and 
            not s.get('attributes', {}).get('disabled_by')
        ]
        
    else:
        filtered_entities = [
            s for s in all_states
            if s.get('entity_id') and 
            not s.get('attributes', {}).get('hidden_by') and 
            not s.get('attributes', {}).get('disabled_by')
        ]

    return filtered_entities


async def get_options_for_entity(entity_id: str, lighting_overrides: dict = None) -> list:
    """
    Retrieve the possible options for an entity (e.g., input_select) from lighting_overrides if provided,
    otherwise fall back to Home Assistant.
    """
    # Try to get options from lighting_overrides if available
    if lighting_overrides:
        for device in lighting_overrides.values():
            if device.get("controller") == entity_id:
                # Return effects or scenes if present
                if "effects" in device:
                    return device["effects"]
                if "scenes" in device:
                    return device["scenes"]
    # Fallback to Home Assistant if not found in lighting_overrides
    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']

    msg = {"id": 101, "type": "get_states"}
    resp = await ha_ws_call(msg, ws_url, token)
    states = resp.get('result', [])
    for state in states:
        if state['entity_id'] == entity_id:
            return state.get('attributes', {}).get('options', [])
    return []