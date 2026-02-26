import requests

def update_divoom(emoji: str) -> dict:
    """
    Update the Divoom Max to display an emoji by calling the local Divoom server.
    Args:
        emoji (str): The emoji to display.
    Returns:
        dict: Result or status message from the Divoom server.
    """
    try:
        response = requests.post(
            "http://host.docker.internal:5551/send",
            json={"emoji": emoji},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}
