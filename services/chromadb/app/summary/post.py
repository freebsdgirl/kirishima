"""
This module defines the FastAPI router and endpoint for adding a summary to a ChromaDB collection with an embedding.

Functions:
    summary_add(request: Summary, collection = Depends(get_collection)):
        Handles the creation of a new summary by:
        - Validating the presence of a user ID in the request metadata.
        - Removing any existing summaries of the same type for the user.
        - Generating an embedding for the summary content.
        - Adding the new summary to the ChromaDB collection with its metadata and embedding.

    HTTPException: If the user ID is missing from the request metadata (400 Bad Request).
"""

from app.summary.util import get_collection
from app.embedding import get_embedding

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.summary import Summary
from shared.models.embedding import EmbeddingRequest

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.post("/summary", response_model=Summary)
async def summary_add(request: Summary, collection = Depends(get_collection)) -> Summary:
    """
    Add a summary to the ChromaDB collection with embedding.

    This endpoint handles creating a new summary by:
    - Validating the user ID is present
    - Removing any existing summaries of the same type for the user
    - Generating an embedding for the summary content
    - Adding the new summary to the collection with its metadata and embedding

    Args:
        request (Summary): The summary to be added, containing content and metadata
        collection: The ChromaDB collection to add the summary to

    Returns:
        dict: A message confirming successful summary addition

    Raises:
        HTTPException: If the user ID is missing (400 Bad Request)
    """

    if not request.metadata or not request.metadata.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID is required"
        )

    # Find existing summaries for this user and summary_type
    existing = collection.get(
        where={
            "$and": [
                {"user_id": {"$eq": request.metadata.user_id}},
                {"summary_type": {"$eq": request.metadata.summary_type.value}},
            ]
        }
    )
    # Delete existing summaries if any
    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])

    # Create the embedding for the summary
    embedding_request = EmbeddingRequest(
        input=request.content
    )

    embedding = get_embedding(embedding_request)

    # Add the summary to the collection
    clean_metadata = {k: v for k, v in request.metadata.model_dump().items() if v is not None}
    collection.add(
        ids=[request.id],
        documents=[request.content],
        metadatas=[clean_metadata],
        embeddings=[embedding]
    )

    return request
