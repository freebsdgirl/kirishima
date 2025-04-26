"""
This module provides an API endpoint for generating text embeddings using ChromaDB.

It defines a FastAPI router with a single POST endpoint `/embedding` that accepts an
EmbeddingRequest and returns a list of embedding vector values. The endpoint retrieves
the ChromaDB service address via Consul, sends the input text for embedding generation,
and handles errors related to service availability and processing.

Modules and dependencies:
- shared.config: Provides configuration constants (e.g., TIMEOUT).
- shared.log_config: Logger configuration for consistent logging.
- shared.models.embedding: EmbeddingRequest model definition.
- httpx: For making asynchronous HTTP requests.
- shared.consul: Service discovery for ChromaDB.
- fastapi: API routing and exception handling.

    HTTPException: For invalid input, service unavailability, or processing errors.
"""

from shared.config import TIMEOUT

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from shared.models.embedding import EmbeddingRequest

import httpx
import shared.consul

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/embedding", response_model=list)
async def embedding(input: EmbeddingRequest) -> list:
    """
    Endpoint for generating text embeddings via ChromaDB.

    Retrieves the ChromaDB service address and sends a request to generate embeddings
    for the provided text. Handles potential service unavailability and errors.

    Args:
        text (str): The input text to generate embeddings for.

    Returns:
        List[float]: A list of embedding vector values.

    Raises:
        HTTPException: With appropriate status codes for service or processing errors.
    """

    try: 
        request = input.model_dump()

    except:
        logger.error(f"Error converting request to JSON format: {input}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input format."
        )

    try:
        chromadb_host, chromadb_port = shared.consul.get_service_address('chromadb')
        if not chromadb_host or not chromadb_port:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB service is unavailable."
            )

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"http://{chromadb_host}:{chromadb_port}/embedding",
                json={"input": request['input']}
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding model error"
            )

        return response.json()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating embedding: {e}"
        )
