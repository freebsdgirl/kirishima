"""
This module provides an API endpoint for generating dense vector embeddings from text input
using a pre-configured SentenceTransformer model. The embeddings can be used for tasks such
as semantic similarity and other natural language processing applications.
Modules:
    - shared.log_config: Provides logging functionality.
    - app.config: Contains application-specific configurations.
    - shared.models.embedding: Defines the data model for embedding requests.
    - sentence_transformers: Library for generating text embeddings using transformer models.
    - fastapi: Framework for building API endpoints.
    router (APIRouter): FastAPI router for defining API endpoints.
Functions:
    - get_embedding(request: EmbeddingRequest) -> list:
        Generates a dense vector embedding for the given text input and returns it as a list of floats.
"""

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

import app.config

from shared.models.embedding import EmbeddingRequest

from sentence_transformers import SentenceTransformer

from fastapi import HTTPException, status, APIRouter
router = APIRouter()


"""
Initialize a SentenceTransformer model for generating text embeddings.

Uses the model specified in the configuration to convert text into dense vector representations
that can be used for semantic similarity and embedding tasks.

Attributes:
    model (SentenceTransformer): Pre-configured transformer model for generating text embeddings.
"""
model = SentenceTransformer(app.config.CHROMADB_MODEL_NAME)


@router.post("/embedding", response_model=list)
def get_embedding(request: str) -> list:
    """
    Generate a dense vector embedding for the given text input.
    
    Args:
        request (EmbeddingRequest): The text input to be converted into a vector representation.
    
    Returns:
        list: A list of float values representing the text embedding.
    """
    try: 
        logger.debug(f"/embedding Request: {request}")

    except:
        logger.error("Error converting request to JSON format.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input format."
        )

    try:
        # Generate the embedding using the model
        embedding = model.encode(request).tolist()

    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating embedding: {e}"
        )

    return embedding
