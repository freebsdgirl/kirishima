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
from app.util import ha_ws_call, get_ws_url
from app.services.device import _list_devices, _get_device_entities
from app.services.entity import _get_entity, _get_options_for_entity
from app.services.media import _build_media_context_for_llm

from shared.models.proxy import SingleTurnRequest
from shared.models.smarthome import UserRequest
from shared.prompt_loader import load_prompt

from shared.log_config import get_logger
logger = get_logger(f"smarthome.{__name__}")

import httpx
import json
import os
from datetime import datetime

from fastapi import HTTPException, status


async def _handle_media_recommendation(request: UserRequest, media_types: list, devices: list) -> dict:
    """
    Handle media recommendation requests using user's consumption history.
    """
    try:
        logger.debug(f"Building media context for recommendation: {media_types}")
        
        # Build context with user's media preferences
        media_context = _build_media_context_for_llm(request.full_request, devices, media_types)
        logger.debug(f"Media context built: {media_context}")
        
        # Load the media recommendation prompt
        prompt_content = load_prompt("smarthome/user_request/media_recommendations.j2", media_context)
        logger.debug(f"Media recommendation prompt generated")
        
        singleturn_request = SingleTurnRequest(
            model="smarthome",
            prompt=prompt_content
        )

        proxy_port = os.getenv("PROXY_PORT", 4205)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"http://proxy:{proxy_port}/api/singleturn",
                json=singleturn_request.model_dump()
            )
            response.raise_for_status()
        
        recommendation_data = response.json()
        logger.debug(f"Media recommendation LLM response: {recommendation_data}")
        
        try:
            recommendations_obj = json.loads(recommendation_data['choices'][0]['content'])
            logger.info(f"Generated media recommendations: {recommendations_obj}")
            
            return {
                "intent": "MEDIA_RECOMMENDATION",
                "media_types": media_types,
                "recommendations": recommendations_obj.get("recommendations", []),
                "device_ids": recommendations_obj.get("device_ids", []),
                "reasoning": recommendations_obj.get("reasoning", ""),
                "status": "success"
            }
            
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Failed to parse media recommendation response: {e}")
            logger.debug(f"Raw recommendation response: {recommendation_data.get('choices', [{}])[0].get('content', 'No content')}")
            return {"error": "Failed to generate media recommendations."}
            
    except Exception as e:
        logger.exception(f"Error handling media recommendation: {e}")
        return {"error": f"Failed to process media recommendation: {str(e)}"}


async def _user_request(request: UserRequest) -> dict:
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
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    TIMEOUT = _config["timeout"]

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
    response = await _list_devices()

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

    prompt = load_prompt("smarthome", "user_request", "device_matching", 
                        full_request=full_request, 
                        name=name, 
                        devices=json.dumps(devices, indent=2))

    singleturn_request = SingleTurnRequest(
        model="smarthome",
        prompt=prompt
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            proxy_port = os.getenv("PROXY_PORT", 4205)
            response = await client.post(
                f"http://proxy:{proxy_port}/api/singleturn",
                json=singleturn_request.model_dump()
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
        logger.debug(f"Device matching LLM response: {data}")

        try:
            device_matches_obj = json.loads(data['choices'][0]['content'])
            logger.debug(f"Parsed device matching response: {device_matches_obj}")
            
            intent = device_matches_obj.get("intent", "DEVICE_CONTROL")
            device_matches = device_matches_obj.get("devices", [])
            reasoning = device_matches_obj.get("reasoning", "")
            
            logger.info(f"Request intent: {intent}, matched devices/types: {device_matches}, reasoning: {reasoning}")
            
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Failed to parse device matching response: {e}")
            logger.debug(f"Raw LLM response content: {data.get('choices', [{}])[0].get('content', 'No content')}")
            return {"error": "Failed to parse device matching response."}

        # Handle different intents
        if intent == "MEDIA_RECOMMENDATION":
            logger.info(f"Processing media recommendation request for media type(s): {device_matches}")
            return await _handle_media_recommendation(request, device_matches, devices)
        
        elif intent == "MEDIA_CONTROL":
            logger.info(f"Processing media control request for devices: {device_matches}")
            # Continue with normal device control flow but for media devices
        
        elif intent == "DEVICE_CONTROL":
            logger.info(f"Processing device control request for devices: {device_matches}")
            # Continue with normal device control flow
        
        else:
            logger.warning(f"Unknown intent: {intent}, defaulting to device control")

        if not device_matches:
            logger.warning("No matching devices found after intent processing")
            return {"error": "No matching devices found."}

        logger.debug(f"Matched device_ids: {device_matches}")

        # so now we have this list of device_ids. we need to get entities for these devices.
        device_entities = await _get_device_entities(device_matches)

        device_info_by_id = {d["device_id"]: d for d in devices}
        # Gather all controller entity_ids from devices that have a controller
        controller_entity_ids = [info.get("controller") for info in device_info_by_id.values() if info.get("controller")]
        controller_states = {}
        if controller_entity_ids:
            states = await _get_entity(controller_entity_ids)
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
                device["controller_values"] = await _get_options_for_entity(controller, lighting_overrides)

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
            related_states = await _get_entity(related_controller_entity_ids)
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
    prompt = load_prompt("smarthome", "user_request", "action_generation",
                        current_time=current_time,
                        full_request=full_request,
                        device_entities=json.dumps(device_entities, indent=2),
                        related_device_entities=json.dumps(related_device_entities, indent=2))

    singleturn_request = SingleTurnRequest(
        model="smarthome",
        prompt=prompt
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            proxy_port = os.getenv("PROXY_PORT", 4205)
            response = await client.post(
                f"http://proxy:{proxy_port}/api/singleturn",
                json=singleturn_request.model_dump()
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