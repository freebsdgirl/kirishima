from app.util import _open_conn
from shared.models.ledger import TopicResponse, TopicByIdRequest
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")


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