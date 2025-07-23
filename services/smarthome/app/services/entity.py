from app.util import get_ws_url, ha_ws_call
from typing import List, Dict
import json


async def _list_entities(filtered: bool = True) -> List[Dict]:
    """
    Retrieve entities from the Home Assistant entity registry, returning only
    device_id, entity_id, and name (preferring 'name', falling back to 'original_name').

    Args:
        filtered (bool, optional): If True, filters entities by the configured label 
        and excludes disabled or hidden entities. Defaults to False.

    Returns:
        List[Dict]: A list of entity dictionaries with selected fields.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

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


async def _get_entity(entity_ids: List[str]) -> List[Dict]:
    """
    Retrieve the current states for a specific list of entity IDs from Home Assistant.
    
    Args:
        entity_ids (List[str]): A list of entity IDs to retrieve states for.
    
    Returns:
        List[Dict]: A list of state dictionaries for the specified entity IDs, 
        including their current attributes and values.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
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


async def _get_options_for_entity(entity_id: str, lighting_overrides: dict = None) -> list:
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
    with open('/app/config/config.json') as f:
        _config = json.load(f)
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


async def _get_states(filtered: bool = True) -> List[Dict]:
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
    with open('/app/config/config.json') as f:
        _config = json.load(f)
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