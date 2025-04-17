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
        logger.debug(f"/embedding Request:\n{input.model_dump_json(indent=4)}")
    except:
        logger.error("Error converting request to JSON format.")
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

        async with httpx.AsyncClient() as client:
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
