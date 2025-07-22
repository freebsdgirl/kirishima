"""
This module defines FastAPI routes for user-related operations in the ledger service.

Routes:
    - DELETE /{user_id}: Delete all messages for a specific user, or filter by period and date.
    - GET /{user_id}/messages: Retrieve messages for a user, with optional filtering by period, date, or explicit timestamps.
    - GET /{user_id}/messages/last: Get the timestamp of the most recent message sent by a user.
    - GET /{user_id}/messages/untagged: Retrieve all untagged messages for a user, excluding tool messages and empty assistant messages.
    - POST /{user_id}/sync: Synchronize a user's message buffer with the server-side ledger, handling deduplication, edits, and appends.
    - GET /active: Retrieve a list of unique user IDs with messages in the database.

Dependencies:
    - shared.models.ledger: Data models for requests and responses.
    - shared.log_config: Logger configuration.
    - app.services.user.*: Service functions for user message operations.
    - fastapi: API framework.

All endpoints are registered under the APIRouter instance `router`.
"""

from shared.models.ledger import (
    DeleteSummary,
    DeleteUserMessagesRequest,
    UserMessagesRequest,
    CanonicalUserMessage,
    UserUntaggedMessagesRequest,
    UserLastMessageRequest,
    RawUserMessage,
    UserSyncRequest
)

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from app.services.user.delete_messages import _delete_user_messages
from app.services.user.get_messages import _get_user_messages
from app.services.user.get_active import _get_active_users
from app.services.user.get_untagged_messages import _get_user_untagged_messages
from app.services.user.get_last_timestamp import _get_last_message_timestamp
from app.services.user.sync import _sync_user_buffer_helper

from typing import Optional, List
from fastapi import APIRouter, Path, Query, Body, BackgroundTasks

router = APIRouter()

@router.delete("/{user_id}", response_model=DeleteSummary)
def delete_user_buffer(
    user_id: str = Path(...),
    period: Optional[str] = Query(None, description="Time period to filter messages (e.g., 'morning', 'afternoon', etc.)"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. Defaults to today."),
) -> DeleteSummary:
    """
    Delete all messages for a specific user, or only those in a given period and date.

    Args:
        user_id (str): The unique identifier of the user whose messages will be deleted.
        period (Optional[str]): Time period to filter messages.
        date (Optional[str]): Date in YYYY-MM-DD format.

    Returns:
        DeleteSummary: An object containing the count of deleted messages.
    """
    request = DeleteUserMessagesRequest(user_id=user_id, period=period, date=date)
    deleted_count = _delete_user_messages(request)
    return DeleteSummary(deleted=deleted_count)


@router.get("/{user_id}/messages", response_model=List[CanonicalUserMessage])
def get_user_messages(
    user_id: str = Path(...),
    period: Optional[str] = Query(None, description="Time period to filter messages (e.g., 'morning', 'afternoon', etc.)"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. Defaults to today unless time is 00:00, then yesterday."),
    start: Optional[str] = Query(None, description="Start timestamp (ISO 8601, e.g. '2025-06-29T00:00:00'). If provided, overrides period/date filtering."),
    end: Optional[str] = Query(None, description="End timestamp (ISO 8601, e.g. '2025-06-29T23:59:59'). If provided, overrides period/date filtering."),
) -> List[CanonicalUserMessage]:
    """
    Retrieve messages for a specific user, optionally filtered by time period, date, or explicit start/end timestamps.
    """
    request = UserMessagesRequest(
        user_id=user_id,
        period=period,
        date=date,
        start=start,
        end=end
    )
    return _get_user_messages(request)


@router.get("/{user_id}/messages/last", response_model=str)
def get_last_message_timestamp(user_id: str = Path(...)) -> str:
    """
    Retrieves the timestamp of the most recent message sent by a specific user.

    Args:
        user_id (str): The unique identifier of the user.

    Returns:
        str: The timestamp of the latest message sent by the user in the 'created_at' field,
             or an empty string if no messages are found.
    """
    request = UserLastMessageRequest(user_id=user_id)
    return _get_last_message_timestamp(request)


@router.get("/{user_id}/messages/untagged", response_model=List[CanonicalUserMessage])
def get_user_untagged_messages(user_id: str = Path(...)) -> List[CanonicalUserMessage]:
    """
    Retrieve all untagged messages for a given user from the database.

    This function fetches messages from the `user_messages` table where the `user_id` matches
    the provided value and `topic_id` is NULL (untagged). The messages are ordered by their `id`.
    It filters out messages where the role is 'tool' or where the role is 'assistant' and the content is empty.

    Args:
        user_id (str): The ID of the user whose untagged messages are to be retrieved.

    Returns:
        List[CanonicalUserMessage]: A list of CanonicalUserMessage objects representing the user's untagged messages,
        excluding tool messages and assistant messages with empty content.
    """
    request = UserUntaggedMessagesRequest(user_id=user_id)
    return _get_user_untagged_messages(request)


@router.post("/{user_id}/sync", response_model=List[CanonicalUserMessage])
def sync_user_buffer(
    user_id: str = Path(..., description="Unique user identifier"),
    snapshot: List[RawUserMessage] = Body(..., embed=True),
    background_tasks: BackgroundTasks = None
) -> List[CanonicalUserMessage]:
    """
    Synchronize a user's message buffer with the server-side ledger.

    This endpoint handles complex message buffer synchronization logic for a given user, supporting:
    - Deduplication of messages
    - Handling consecutive user messages
    - Editing assistant messages
    - Appending new messages
    - Optional result limiting

    Args:
        user_id (str): Unique identifier for the user
        snapshot (List[RawUserMessage]): Snapshot of user and assistant messages
        background_tasks (BackgroundTasks, optional): Background task handler

    Returns:
        List[CanonicalUserMessage]: Synchronized and processed message buffer
    """
    request = UserSyncRequest(user_id=user_id, snapshot=snapshot)
    return _sync_user_buffer_helper(request)


@router.get("/active")
async def trigger_summaries_for_inactive_users():
    """
    Retrieve a list of unique user IDs from the user messages database.

    This endpoint returns all distinct user IDs that have messages in the database.
    Useful for identifying active or potentially inactive users across the system.

    Returns:
        List[str]: A list of unique user IDs found in the user messages database.
    """
    return _get_active_users()
