"""
This module provides an API endpoint to retrieve a topic by its unique ID.
It defines a FastAPI router with a GET endpoint at '/topics/{topic_id}' that returns the topic's details if it exists.
The helper function '_get_topic_by_id' interacts with the database to fetch the topic's 'id' and 'name'.
If the topic does not exist, a 404 Not Found HTTPException is raised.
Endpoints:
    GET /topics/{topic_id}: Retrieve a topic by its ID.
Functions:
    _get_topic_by_id(topic_id: str) -> TopicResponse: Fetches topic details from the database.
    get_topic_by_id(topic_id: str): API endpoint to get topic details by ID.
"""
from fastapi import APIRouter, HTTPException, status
from app.util import _open_conn
from app.topic.util import topic_exists
from shared.models.ledger import TopicResponse, TopicByIdRequest
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

router = APIRouter()


def _get_topic_by_id(request: TopicByIdRequest) -> TopicResponse:
    """
    Helper function to retrieve a topic by its ID.
    
    Args:
        request: TopicByIdRequest containing topic_id
    
    Returns:
        TopicResponse: A response object containing the topic's 'id' and 'name'.
    
    Raises:
        HTTPException: If the topic does not exist, raises a 404 Not Found error.
    """
    topic_id = request.topic_id
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM topics WHERE id = ?", (topic_id,))
        row = cur.fetchone()
        return TopicResponse(id=row[0], name=row[1])

@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic_by_id(topic_id: str):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    request = TopicByIdRequest(topic_id=topic_id)
    return _get_topic_by_id(request)