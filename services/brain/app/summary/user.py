from shared.models.ledger import SummaryRequest

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from app.util import get_user_alias

import httpx

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

# problem:
# currently, summaries are created by a backgroundtask spawned by the ledger
# service when the sync endpoint is called. summaries will not live on the
# ledger's database permanently - eventually they are getting moved to chroma.
# only brain should takl to chroma.
# also, when summaries are getting created, we need to pull the first alias of
# the given user_id from the contacts service, and i don't really want proxy to
# do that.
# the reasonable solution is to create a new function on the ledger service that
# will be called by backgroundtask when sync is updated. this function will 
# determine if the summary should be created or not, and if so, it will take the
# list of messages to be summarized and send it to a new endpotin on brain, which
# will do the following:
# - query contacts for the first alias of the user
# - send the list of messages along with the user alias to the proxy service's
# summarization endpoint.
# - receive the summary from proxy
# - return the summary to the ledger service.
# future plans will be to call chromadb endpoints instead, but we haven't created
# those yet.
# we'll also want to create new endpoints for semantic search of those summaries.

@router.post("/summary/user", status_code=status.HTTP_201_CREATED)
async def create_summary_user(request: SummaryRequest):
    """
    Create a summary for a user based on the provided request data.
    """
    if not request.messages or not request.messages[0].user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID is required"
        )
    user_id = request.messages[0].user_id
    logger.debug(f"Creating summary for user {user_id} with messages: {request.messages}")

    # Get the first alias of the user from contacts service
    user_alias = await get_user_alias(user_id)
    if not user_alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User alias not found"
        )

    # Prepare the payload for the proxy
    payload = request.model_dump()
    payload["user_alias"] = user_alias

    # Send the request to the proxy service
    try:
        proxy_address, proxy_port = shared.consul.get_service_address('proxy')
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"http://{proxy_address}:{proxy_port}/summary/user", json=payload)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Error creating summary"
        )