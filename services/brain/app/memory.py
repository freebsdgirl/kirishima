"""
Memory Management API Router

This module provides a FastAPI router for managing memory storage operations, including:
- Adding new memories with embeddings
- Searching for memory IDs
- Listing memories by component
- Retrieving, updating, and deleting individual memories

The router interfaces with a memory storage service, handling various CRUD operations 
with logging and error handling. It uses sentence transformers to generate embeddings 
for semantic memory storage and retrieval.

Key Features:
- Supports creating, reading, updating, and deleting memories
- Generates semantic embeddings for memory content
- Provides detailed logging for memory operations
- Handles communication with an external memory storage service
"""
import app.config

from shared.log_config import get_logger
logger = get_logger(__name__)

from pydantic import BaseModel
import requests
from json import JSONDecodeError
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Response
from fastapi.responses import JSONResponse
router = APIRouter()

from sentence_transformers import SentenceTransformer
embedding_model = SentenceTransformer("intfloat/e5-small-v2")

import os
chromadb_host = os.getenv("CHROMADB_HOST", "localhost")
chromadb_port = os.getenv("CHROMADB_PORT", "4206")
chromadb_url = f"http://{chromadb_host}:{chromadb_port}"


class RawMemoryRequest(BaseModel):
    """
    Pydantic model representing a memory request with details for storing a memory.

    Args:
        memory (str): The content of the memory to be stored.
        component (str): The component or 'mode' associated with the memory.
        priority (float, optional): The priority of the memory, ranging from 0 to 1.
    """
    memory: str
    component: str
    priority: float


def get_embedding(text: str) -> list:
    """
    Generates text embeddings using the intfloat/e5-small-v2 Sentence Transformer model.

    Initializes a pre-trained embedding model and provides a function to convert text 
    into dense vector representations suitable for semantic similarity and machine learning tasks.

    Args:
        text (str): The input text to be converted into an embedding vector.

    Returns:
        list: A list of floating-point numbers representing the text's semantic embedding.
    """
    # Initialize the embedding model from Transformers (intfloat/e5-small-v2)
    return embedding_model.encode(text).tolist()


@router.post("/memory", response_model=JSONResponse)
async def memory_add(request_data: RawMemoryRequest) -> JSONResponse:
    """
    Add a new memory to the memory storage service.

    Generates embeddings for the memory, creates a payload with memory details,
    and sends a POST request to the memory storage service. Logs the result
    and handles potential errors.

    Args:
        request_data (MemoryRequest): Details of the memory to be stored, including
            memory content, component, and priority.

    Returns:
        JSONResponse: A success or error message indicating the result of memory storage.

    Raises:
        HTTPException: If there's an error communicating with the memory storage service.
    """
    logger.debug(f"💡 Creating memory: {request_data.memory}")

    # Generate embeddings for the new memory
    embedding = get_embedding(request_data.memory)

    payload = {
        "memory": request_data.memory, 
        "component": request_data.component,
        "priority": request_data.priority,
        "embedding": embedding
    }

    try:
        # Send a POST request to the memory storage service
        response = requests.post(f"{chromadb_url}/memory", json=payload)

        if response.status_code != status.HTTP_201_CREATED:
            logger.error(f"🚫 Failed to store memory: {request_data.memory}, code: {response.status_code}")

            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        if response.status_code == status.HTTP_201_CREATED:
            logger.info(f"💡 Memory stored successfully: {request_data.memory}")

            try:
                result = response.json()

            except JSONDecodeError:
                logger.error(f"🚫 Failed to decode JSON response.")

                return HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="JSON decode error."
                ) 

        return JSONResponse(
            content={
                "message": "Memory added successfully",
                "id": result["id"],
                "timestamp": result["timestamp"]
            },
            status_code=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )


class SearchForId(BaseModel):
    """
    Pydantic model representing the search request payload for finding a memory document by input text.
    
    Attributes:
        input (str): The text input to search for in memory documents.
    """
    input: str


@router.post("/memory/search/id", response_model=JSONResponse)
async def memory_search_for_id(request: SearchForId) -> str:
    """
    Search for a memory's unique identifier based on input text.

    Sends a request to the memory storage service to find the ID of a memory
    matching the provided input. Returns the memory's ID if found, otherwise
    raises an appropriate HTTP exception.

    Args:
        request (SearchForId): Contains the input text to search for.

    Returns:
        JSONResponse: A response containing the memory's unique identifier.

    Raises:
        HTTPException: If the memory ID cannot be retrieved (404 if not found,
        502 for service communication errors).
    """
    logger.debug(f"🔍 Received search for ID query: {request.input}")

    try:
        payload = {
            "input": request.input
        }

        # send a GET request to the memory storage service
        response = requests.post(f"{chromadb_url}/memory/search/id", json=payload)

        if response.status_code == status.HTTP_200_OK:
            logger.info(f"🔍 ID found for memory {response.content}")

            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )

        else:
            logger.error(f"🚫 Failed to retrieve id for {request.input}, code: {response.status_code}")

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to find ID for memory"
            )

    except Exception as e: 
        logger.error(f"🛑 ERROR querying ChromaDB API: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"🛑 ERROR querying ChromaDB API: {str(e)}"
        )


@router.get("/memory", response_model=JSONResponse)
async def memory_list_by_component(component: str, limit: int = 100) -> JSONResponse:
    """
    Retrieve memories for a specific component from the memory storage service.

    Sends a GET request to the memory storage service to fetch memories associated
    with the specified component. Handles potential errors such as missing component
    or service communication issues.

    Args:
        component (str): The name of the component to retrieve memories for.

    Returns:
        JSONResponse: A list of memories for the specified component.
            { 
                id: int
                document: str
                metadata: {
                    timestamp: str
                    priority: float
                    component: str
                }
            }

    Raises:
        HTTPException: If no component is specified or if there's an error
        communicating with the memory storage service.
    """
    logger.debug(f"📚 Listing memories for {component}")

    if not component:
        logger.error("🚫 Error listing memories: no component specified")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing component parameter"
        )

    try:
        response = requests.get(f"{chromadb_url}/memory?component={component}&limit={limit}")

        if response.status_code == status.HTTP_200_OK:
            logger.info(f"📚 Memories listed successfully for {component}")

            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )

        else:
            logger.error(f"🚫 Failed to retrieve memories for {component}, code: {response.status_code}")

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch memories"
            )

    except Exception as e: 
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"🛑 ERROR querying ChromaDB: {str(e)}"
        )


@router.get("/memory/{id}", response_model=JSONResponse)
async def memory_list_id(id: str) -> JSONResponse:
    """
    Retrieve a specific memory by its unique identifier.

    Sends a GET request to the memory storage service to fetch a single memory
    based on the provided memory ID. Handles potential errors such as service
    communication issues.

    Args:
        id (str): The unique identifier of the memory to retrieve.

    Returns:
        JSONResponse: A single memory object with details.
            { 
                id: int
                document: str
                metadata: {
                    timestamp: str
                    priority: float
                    component: str
                }
            }

    Raises:
        HTTPException: If there's an error communicating with the memory storage service
        or if the memory cannot be retrieved.
    """
    logger.debug(f"📚 Listing memory id: {id}")

    try:
        # send a GET request to the memory storage service
        response = requests.get(f"{chromadb_url}/memory/{id}")

        if response.status_code == status.HTTP_200_OK:
            logger.info(f"📚 Memory listed successfully for {id}")

            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )

        else:
            logger.error(f"🚫 Failed to retrieve memory {id}, code: {response.status_code}")

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch memory"
            )

    except Exception as e: 
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"🛑 ERROR querying ChromaDB: {str(e)}"
        )


@router.delete("/memory/{id}", response_class=Response)
async def memory_delete_by_id(id: str) -> Response:
    """
    Delete a specific memory by its unique identifier.

    Sends a DELETE request to the memory storage service to remove a single memory
    based on the provided memory ID. Handles potential errors such as service
    communication issues or invalid memory ID.

    Args:
        id (str): The unique identifier of the memory to delete.

    Returns:
        Response: A 204 No Content response if the memory is successfully deleted.

    Raises:
        HTTPException: If there's an error communicating with the memory storage service,
        the memory cannot be deleted, or there are JSON decoding issues.
    """
    logger.debug(f"🗑️ Deleting memory id: {id}")

    try:
        response = requests.delete(f"{chromadb_url}/memory/{id}")

        if response.status_code != status.HTTP_204_NO_CONTENT:
            logger.error(f"🚫 Failed to delete memory: {id}, code: {response.status_code}")

            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        if response.status_code == status.HTTP_204_NO_CONTENT:
            logger.info(f"🗑️ Memory deleted successfully: {id}")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"🛑 ERROR querying ChromaDB: {str(e)}"
        )


@router.put("/memory/{id}", response_model=JSONResponse)
async def memory_replace_by_id(id: str, request_data: RawMemoryRequest) -> JSONResponse:
    """
    Replace an existing memory entry by its unique identifier.

    Sends a PUT request to the memory storage service to completely replace a memory
    entry with new data. Automatically generates a new embedding for the memory text.

    Args:
        id (str): The unique identifier of the memory to replace
        request_data (MemoryRequest): Complete replacement data for the memory entry

    Returns:
        JSONResponse: Confirmation of successful memory replacement with status 200

    Raises:
        HTTPException: If there's an error communicating with the memory storage service
        or the memory cannot be replaced.
    """
    logger.debug(f"💾 Replacing memory id: {id}")

    try:
        payload = {
            "id": id,
            "memory": request_data.memory,
            "component": request_data.component,
            "priority": request_data.priority,
            "embedding": get_embedding(request_data.memory)
        }

        response = requests.put(f"{chromadb_url}/memory/{id}", json=payload)

        if response.status_code != status.HTTP_200_OK:
            logger.error(f"🚫 Failed to replace memory: {id}, code: {response.status_code}")

            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        logger.info(f"💾 Memory replaced successfully: {id}")
        return JSONResponse(
            content={
                "message": "Memory replaced",
                "id": id
            },
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"🛑 ERROR querying ChromaDB: {str(e)}"
        )


class MemoryPatchRequest(BaseModel):
    """
    Pydantic model representing the optional fields for partially updating a memory entry.
    
    Allows selective updates to a memory's text, component, or priority without requiring
    all fields to be present. Fields set to None will not be modified in the storage service.
    
    Attributes:
        memory (Optional[str]): The updated text content of the memory.
        component (Optional[str]): The updated component associated with the memory.
        priority (Optional[float]): The updated priority level of the memory.
    """
    memory: Optional[str] = None
    component: Optional[str] = None
    priority: Optional[float] = None


@router.patch("/memory/{id}", response_model=JSONResponse)
async def memory_patch_by_id(id: str, patch_data: MemoryPatchRequest) -> JSONResponse:
    """
    Partially update a memory entry by its ID.

    Allows updating specific fields of a memory entry in the storage service.
    Supports updating memory text, component, and priority. When memory text is updated,
    a new embedding is automatically generated.

    Args:
        id (str): The unique identifier of the memory to patch
        patch_data (MemoryPatchRequest): Partial update data for the memory entry

    Returns:
        JSONResponse: Confirmation of successful memory patch with status 200
    """
    logger.debug(f"🩹 Patching memory id: {id}")

    try:
        update_fields = patch_data.dict(exclude_unset=True)

        if "memory" in update_fields:
            update_fields["embedding"] = get_embedding(update_fields["memory"])

        update_fields["id"] = id  # ensure ID is included

        response = requests.patch(f"{chromadb_url}/memory/{id}", json=update_fields)

        if response.status_code != status.HTTP_200_OK:
            logger.error(f"🚫 Failed to patch memory: {id}, code: {response.status_code}")

            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        logger.info(f"🩹 Memory patched successfully: {id}")
        return JSONResponse(
            content={
                "message": "Memory patched",
                "id": id
            },
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"🛑 ERROR querying ChromaDB: {str(e)}"
        )
