from app.services.entity import _list_entities, _get_entity

from fastapi import APIRouter

router = APIRouter()


@router.get("", response_model=list)
async def list_entities() -> list:
    """
    Retrieves a list of all entities in Home Assistant.

    Returns:
        list: A list of entity names.
    """
    return await _list_entities()


@router.get("/{entity_id}")
async def get_entity(entity_id: str):
    """
    Retrieves details for a specific entity by its ID.

    Args:
        entity_id (str): The ID of the entity to retrieve.
    Returns:
        dict: A dictionary containing the entity's details.
    """
    return await _get_entity([entity_id])