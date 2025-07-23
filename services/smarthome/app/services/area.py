from app.util import get_ws_url, ha_ws_call
from typing import List, Dict
import json

async def _list_area() -> List[str]:
    """
    Retrieve all area names from the Home Assistant area registry.
    
    Returns:
        List[str]: A list of area names registered in Home Assistant.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    msg = {"id": 1, "type": "config/area_registry/list"}
    resp = await ha_ws_call(msg, ws_url, token)
    return [area['name'] for area in resp.get('result', [])]


async def _list_devices_in_area(area_name: str, filtered: bool = True) -> List[Dict]:
    """
    Retrieve all enabled devices within a specific area by area name.
    
    Args:
        area_name (str): The name of the area to retrieve devices from.
        filtered (bool, optional): If True, filters devices by the configured label.
    
    Returns:
        List[Dict]: A list of enabled device dictionaries located in the specified area.
        Returns an empty list if the area is not found.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)

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