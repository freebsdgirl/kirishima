from app.config import CHROMADB_URL

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import httpx

from shared.log_config import get_logger
logger = get_logger(__name__)

router = APIRouter()


class EmbeddingRequest(BaseModel):
    input: str


@router.post("/embeddings")
async def create_embedding(request: EmbeddingRequest):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CHROMADB_URL}/embeddings",  # ✅ Calls the local embedding server
                json={"input": request.input}
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=response.status_code,
                detail="Embedding model error"
            )

        return response.json()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
