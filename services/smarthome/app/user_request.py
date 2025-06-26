"""
This module provides an API endpoint for processing user requests related to smart home device control and automation.
Key functionalities:
- Loads device overrides from a configuration file (lighting.json).
- Retrieves available devices and their metadata from the system.
- Uses an OpenAI-powered model to intelligently match user requests to devices.
- Fetches entities and states for matched devices, including controller information and available options.
- Considers related devices for context, especially for lighting scenarios.
- Generates and executes Home Assistant actions based on the user's request, device states, and contextual information.
- Handles errors and provides detailed reasoning for actions taken or not taken.
Main endpoint:
    POST /user_request
            name (str): The name of the device to match.
            full_request (str): The complete user request for context.
            dict: Result object containing executed actions, reasoning, and status.
"""
from app.util import get_devices, get_entities_for_device, get_states_for_entity_ids, get_options_for_entity, ha_ws_call, get_ws_url

from shared.models.openai import OpenAICompletionRequest
from shared.models.smarthome import UserRequest

from shared.log_config import get_logger
logger = get_logger(f"scheduler.{__name__}")

import httpx
import json
import os

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/user_request")
async def user_request(request: UserRequest) -> dict:
    """
    Retrieve and match devices based on a user request, with intelligent device selection and action execution.
    
    This async function performs the following key steps:
    - Load device overrides from lighting.json
    - Retrieve system devices
    - Use OpenAI to match devices to the user's request
    - Fetch entities and states for matched devices
    - Generate and execute Home Assistant actions based on the request
    
    Args:
        name (str): The name of the device to match
        full_request (str): The complete user request for context
    
    Returns:
        dict: A result object containing executed actions, reasoning, and status
    """

    full_request = request.full_request.strip()
    name = request.name.strip() if request.name else ""

    logger.debug(f"Received user request: {full_request} for device: {name}")
    # Load lighting.json for device overrides
    lighting_path = os.path.join(os.path.dirname(__file__), "lighting.json")
    try:
        with open(lighting_path) as lf:
            lighting_overrides = {item["device_id"]: item for item in json.load(lf)}
    except Exception as e:
        logger.warning(f"Could not load lighting.json: {e}")
        lighting_overrides = {}

    # Get devices (filtered as needed)
    response = await get_devices()

    # Only need device_id, name, notes, type, and controller (if present)
    devices = []
    for device in response:
        did = device["id"]
        if did in lighting_overrides:
            override = lighting_overrides[did]
            devices.append({
                "device_id": did,
                "name": override.get("name", device.get("name")),
                "notes": override.get("notes", ""),
                "type": "light",
                "controller": override.get("controller")
            })
        else:
            devices.append({
                "device_id": did,
                "name": device.get("name"),
                "type": "unknown"
            })

    prompt = f"""The user has made the following request: "{full_request}"
Match the device in this request (name: "{name}") to the devices in the system.
Only include the device_ids in the response.
Multiple devices may match, so return all that match.
Do not return any devices that do not match the request.
Include your reasoning in the response.
Do not include any formatting in the response, just a JSON object with the following structure:
"""+"""
{
    "devices": [
        "device_id_1",
        "device_id_2",
        ...
    ],
    "reasoning": "Your reasoning here"
}
"""+f"""
The devices are as follows:

{devices}
"""

    request = OpenAICompletionRequest(
        model="gpt-4.1-mini",
        prompt=prompt,
        max_tokens=1000,
        temperature=0.3,
        n=1,
        provider="openai"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            api_port = os.getenv("API_PORT", 4200)
            response = await client.post(
                f"http://api:{api_port}/v1/completions",
                json=request.model_dump()
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding to brain: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from multi-turn brain: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error when forwarding to brain: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Connection error to brain: {req_err}"
            )
        except Exception as e:
            logger.exception(f"Error retrieving service address for brain: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error retrieving service address for brain: {e}"
            )
        
        data = response.json()

        try:
            device_matches_obj = json.loads(data['choices'][0]['content'])
            device_matches = device_matches_obj.get("devices", [])
            reasoning = device_matches_obj.get("reasoning", "")
        except (json.JSONDecodeError, TypeError, KeyError):
            return {"error": "No matching devices found."}

        if not device_matches:
            return {"error": "No matching devices found."}

        logger.debug(f"Matched device_ids: {device_matches}")

        # so now we have this list of device_ids. we need to get entities for these devices.
        device_entities = await get_entities_for_device(device_matches)

        device_info_by_id = {d["device_id"]: d for d in devices}
        # Gather all controller entity_ids from devices that have a controller
        controller_entity_ids = [info.get("controller") for info in device_info_by_id.values() if info.get("controller")]
        controller_states = {}
        if controller_entity_ids:
            states = await get_states_for_entity_ids(controller_entity_ids)
            controller_states = {s["entity_id"]: s["state"] for s in states}

        for device in device_entities:
            did = device["device_id"]
            info = device_info_by_id.get(did, {})
            device["notes"] = info.get("notes", "")
            device["type"] = info.get("type", "")
            controller = info.get("controller")
            if controller:
                device["controller"] = controller
                device["controller_state"] = controller_states.get(controller, None)
                device["controller_values"] = await get_options_for_entity(controller, lighting_overrides)

        # Build set of matched device_ids
        matched_device_ids = set(device_matches)

        # Determine if the matched device(s) are type 'light'
        matched_types = {device_info_by_id[did].get("type", "") for did in matched_device_ids if did in device_info_by_id}
        include_lights = "light" in matched_types

        # Find related devices (all other lights in lighting.json, if type is light)
        if include_lights:
            related_devices = [d for d in devices if d["device_id"] not in matched_device_ids and d.get("type") == "light"]
        else:
            related_devices = []

        related_controller_entity_ids = [d.get("controller") for d in related_devices if d.get("controller")]
        related_controller_states = {}
        if related_controller_entity_ids:
            related_states = await get_states_for_entity_ids(related_controller_entity_ids)
            related_controller_states = {s["entity_id"]: s["state"] for s in related_states}

        related_device_entities = []
        for d in related_devices:
            entry = {
                "device_id": d["device_id"],
                "name": d.get("name"),
                "notes": d.get("notes", ""),
            }
            controller = d.get("controller")
            if controller:
                controller_state = related_controller_states.get(controller, None)
                entry["controller_state"] = controller_state

                # Find matching effect/scene description from lighting_overrides
                override = lighting_overrides.get(d["device_id"])
                description = None
                if override:
                    # Prefer effects, fallback to scenes
                    options = override.get("effects") or override.get("scenes") or []
                    for opt in options:
                        if isinstance(opt, dict) and opt.get("name") == controller_state:
                            description = opt.get("description")
                            break
                if description:
                    entry["controller_description"] = description
            related_device_entities.append(entry)

    # now, we take those devices and related devices, and we turn them into another prompt.
    current_time = datetime.now()
    prompt = f"""Date: {current_time}

The user has made the following request: "{full_request}"   

- Lights should have similar effects/scenes.
- Music-related effects should be used when playing music.
- Devices are in a studio apartment, so consider the layout and proximity of devices.
- Coloured lights should be used for ambiance, not just white light.
- Consider the time of day and current activity (if available) when selecting effects.
- Instead of using turn_on/turn_off, select the scene from the controller, if available.
- If multiple scenes match the request, context, and preferences, choose one randomly.

The following devices match the request:
{json.dumps(device_entities, indent=2)}

The following related devices are available for context:
{json.dumps(related_device_entities, indent=2)}

Decide if any action should be taken based on the request, the user preferences, and the devices available.

Output should be the json that will be sent to the home assistant websocket.
Only output the JSON, suitable for being loaded into a python variable via a script. 
JSON should be a list of actions to take, or an empty list if no action is needed.
Do not include any other text.
Do not include any formatting.

Example output:"""+"""
[
    {
        'id': 1, 
        'type': 'call_service', 
        'domain': 'input_select', 
        'service': 'select_option', 
        'service_data': {
            'entity_id': 'input_select.bedroom_scenes', 
            'option': 'Off'
        }
    }
]
"""

    request = OpenAICompletionRequest(
        model="gpt-4.1-mini",
        prompt=prompt,
        max_tokens=1000,
        temperature=0.3,
        n=1,
        provider="openai"
    )

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            api_port = os.getenv("API_PORT", 4200)
            response = await client.post(
                f"http://api:{api_port}/v1/completions",
                json=request.model_dump()
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding to brain: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from multi-turn brain: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error when forwarding to brain: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Connection error to brain: {req_err}"
            )
        except Exception as e:
            logger.exception(f"Error retrieving service address for brain: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error retrieving service address for brain: {e}"
            ) 

        hs_data = response.json()

        try:
            hs_actions = json.loads(hs_data['choices'][0]['content'])
        except (json.JSONDecodeError, TypeError, KeyError):
            return "{\"error\": \"Invalid response from model: "+hs_actions+"\"}"

        # first, let's make sure it's a valid action - it shouldn't be a string or an empty dict
        if isinstance(hs_actions, str) or not isinstance(hs_actions, list):
            return "{\"error\": \"Invalid response from model: "+str(hs_data)+"\"}"
        if not hs_actions:
            return "{\"error\": \"No action to perform.\"}"


        logger.debug(f"Generated Home Assistant actions: {hs_actions}")

    ha_config = _config['homeassistant']
    ws_url = get_ws_url()
    token = ha_config['token']
    
    res = {}
    res["actions"] = []
    res["reasoning"] = reasoning

    for hs_action in hs_actions:
        logger.debug(f"Processing action: {hs_action}")
        if not isinstance(hs_action, dict):
            return {"error": "Invalid action format. Each action should be a dictionary."}
        if 'type' not in hs_action or 'service' not in hs_action:
            return {"error": "Action must contain 'type' and 'service' keys."}

        result = await ha_ws_call(hs_action, ws_url, token)

        res["actions"].append({
            'type': hs_action.get('type', ""),
            'domain': hs_action.get('domain', ""),
            'service': hs_action.get('service', ""),
            'entity_id': hs_action.get('id', ""),
            'service_data': hs_action.get('service_data', {}),
        })

        # Check if the result indicates failure - if so, return early.
        if result.get("success") != True:
            res["status"] = "error"
            res["message"] = result.get("message", "Unknown error occurred.")
            res["details"] = result
            return res


    if result.get("success") == True:
        res["status"] = "success"
        res["message"] = "Action executed successfully."

    logger.debug(f"Final response: {res}")

    return res