from app.services.topic.util import _find_or_create_topic

from shared.models.ledger import TopicCreateRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")


def _create_topic(request: TopicCreateRequest):
    """
    Find an existing topic by name or create a new one if it doesn't exist.
    
    This function prevents duplicate topics with the same name by first checking
    if a topic with the given name already exists. If found, returns the existing
    topic's ID. If not found, creates a new topic and returns its ID.
    
    Args:
        request (TopicCreateRequest): The request containing the topic name.
    
    Returns:
        str: The UUID of the existing or newly created topic.
    """
    return _find_or_create_topic(request.name)