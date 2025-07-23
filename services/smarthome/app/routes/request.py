from app.services.request import _user_request

from shared.models.smarthome import UserRequest

from fastapi import APIRouter

router = APIRouter()

@router.post("/user_request")
async def user_request(request: UserRequest) -> dict:
    """
    Process a user request to match devices and execute actions based on the request.
    
    Args:
        request (UserRequest): The user request containing device name and full request text.
    
    Returns:
        dict: A result object containing executed actions, reasoning, and status.
    """
    return await _user_request(request)