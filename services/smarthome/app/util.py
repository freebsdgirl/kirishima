import json
import httpx
from typing import List, Dict

with open('/app/shared/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


async def get_device_list() -> list:
    """
    Retrieves a list of available smart home devices filtered by label from Home Assistant.

    Returns:
        list: A list of available smart home devices/entities with the configured label.
    """
    if 'homeassistant' in _config:
        ha_config = _config['homeassistant']
    else:
        raise ValueError("Home Assistant configuration not found in shared config.")

    ha_url = ha_config['url']
    ha_token = ha_config['token']
    ha_label = ha_config.get('label', None)
    if not ha_label:
        raise ValueError("No label specified in Home Assistant config.")

    # Ensure URL has protocol
    if not ha_url.startswith('http'):
        ha_url = f'http://{ha_url}'
    api_url = f"{ha_url}/api/states"

    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(api_url, headers=headers)
        resp.raise_for_status()
        entities = resp.json()

    return entities


async def get_filtered_entities() -> List[Dict]:
    """
    Retrieves and filters smart home entities based on a specific label.
    Returns:
        List[Dict]: A list of entities that match the specified label.
    """

    ha_label = _config['homeassistant']['label']
    if not ha_label:
        raise ValueError("No label specified in Home Assistant config.")

    entities = await get_device_list()
    if not entities:
        raise ValueError("No entities found in Home Assistant API response.")

    # Filter entities by custom label attribute
    filtered = [
        entity for entity in entities
        if entity.get('attributes', {}).get('labels') and ha_label in entity['attributes']['labels']
    ]
    return filtered