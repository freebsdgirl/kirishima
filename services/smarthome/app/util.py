"""
Utility functions for interacting with the Home Assistant WebSocket API.

Functions:
    ha_ws_call(message: dict, ws_url: str, token: str) -> dict:
        Asynchronously sends a message to the Home Assistant WebSocket API and returns the response.
        Handles authentication and waits for the response matching the provided message ID.

    get_ws_url() -> str:
        Reads the Home Assistant configuration from a JSON file and constructs the WebSocket URL
        for API communication.
"""
import json
import websockets


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
    with open('/app/config/config.json') as f:
        _config = json.load(f)

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

