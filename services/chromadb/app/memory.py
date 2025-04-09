"""
This router is used to define and organize routes related to memory search, retrieval, addition, 
modification, and deletion in the ChromaDB memory management system.
Routes:
    - POST /search/id: Search for a memory document ID based on input text.
    - POST /memory: Add a new memory to the ChromaDB collection.
    - GET /memory: Retrieve a list of memories for a specific component with a specified limit.
    - GET /memory/{id}: Retrieve a specific memory by its unique identifier.
    - DELETE /memory/{id}: Delete a specific memory by its unique identifier.
    - PUT /memory/{id}: Replace an existing memory with a new memory.
    - PATCH /memory/{id}: Partially update an existing memory.
Models:
    - SearchForId: Represents the search request payload for finding a memory document by input text.
    - MemoryRequest: Represents a request for adding or modifying a memory in the ChromaDB collection.
Error Handling:
    - Returns appropriate HTTP status codes and error messages for various failure scenarios, 
      including 404 Not Found and 500 Internal Server Error.
"""
import app.config

from shared.log_config import get_logger
logger = get_logger(__name__)

from pydantic import BaseModel
import uuid
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime


"""
FastAPI router for handling memory-related API endpoints.

This router is used to define and organize routes related to memory search and retrieval
in the ChromaDB memory management system.
"""
from fastapi import HTTPException, status, Response, APIRouter
router = APIRouter()


class SearchForId(BaseModel):
    """
    Pydantic model representing the search request payload for finding a memory document by input text.
    
    Attributes:
        input (str): The text input to search for in memory documents.
    """
    input: str


@router.post("/search/id", response_model=dict)
def memory_search_for_id(request: SearchForId) -> JSONResponse:
    """
    Search for a memory document ID based on input text.

    Searches the memory collection for a document containing the specified input text.
    Returns the first matching memory's ID or raises a 404 error if no match is found.

    Args:
        request (SearchForId): Contains the input text to search for in memory documents.

    Returns:
        JSONResponse: A response with the first matching memory document's ID.

    Raises:
        HTTPException: 404 if no matching memory is found, or 500 for internal server errors.
    """
    logger.info(f"🔍 Received search for ID query: {request.input}")

    try:
        collection = app.config.client.get_or_create_collection(name=app.config.MEMORY_COLLECTION)
        results = collection.get(
            where_document={"$contains": request.input},
            include=["documents", "metadatas"]
        )

        if results["ids"]:
            return JSONResponse(
                content={"id": results["ids"][0]},
                status_code=status.HTTP_200_OK
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No matching memory found."
            )

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class EmbeddedMemoryEntry(BaseModel):
    """
    Represents a request for adding a memory to the ChromaDB collection.
    
    Attributes:
        memory (str): The content of the memory to be stored.
        component (str): The component associated with the memory.
        priority (float): The priority level of the memory.
        embedding (list): The vector embedding representation of the memory.
    """
    memory: str
    component: str
    priority: float
    embedding: list


@router.post("", response_model=dict)
def memory_add(request_data: EmbeddedMemoryEntry) -> JSONResponse:
    """
    Add a new memory to the ChromaDB collection.

    Handles storing a memory with its associated metadata, generating a unique ID and timestamp.
    Adds the memory to the 'memory' collection with its embedding, priority, and component details.

    Args:
        request_data (MemoryRequest): The memory data to be stored, including memory content, 
        component, priority, and embedding.

    Returns:
        JSONResponse: A response containing the success message, generated memory ID, 
        and timestamp with a 201 Created status code.

    Raises:
        HTTPException: If there's an error querying ChromaDB, with a 500 Internal Server Error status.
    """
    logger.info(f"📜 POST /memory: {request_data.component}: {request_data.memory} ({request_data.priority})")

    try:
        collection = app.config.client.get_or_create_collection(name=app.config.MEMORY_COLLECTION)

        current_time = datetime.now().isoformat()
        memory_id = str(uuid.uuid4())

        collection.add(
            ids=[memory_id],
            documents=[request_data.memory],
            embeddings=[request_data.embedding],
            metadatas=[{
                "timestamp": current_time,
                "priority": request_data.priority,
                "component": request_data.component
            }]
        )

        return JSONResponse(
            content={
                "message": "Memory added successfully",
                "id": memory_id,
                "timestamp": current_time
            },
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=list)
def memory_list(component: str, limit: int) -> list:
    """
    Retrieve a list of memories for a specific component with a specified limit.

    Fetches memories from the ChromaDB collection filtered by component, sorted by timestamp in descending order.

    Args:
        component (str): The component to filter memories by.
        limit (int): The maximum number of memories to retrieve.

    Returns:
        list: A list of memory dictionaries, each containing an ID, document, and metadata.
            Memories are sorted from most recent to oldest.

    Raises:
        HTTPException: 500 if there's an error querying ChromaDB.
    """
    logger.info(f"📜 GET /memory: component: {component} limit: {limit}")

    try:
        COMPONENT_FALLBACKS = {
            "proxy_work": "proxy_default"
        }

        component = COMPONENT_FALLBACKS.get(component, component)

        collection = app.config.client.get_or_create_collection(name=app.config.MEMORY_COLLECTION)

        results = collection.get(
            where={"component": component},
            include=["documents", "metadatas"]
        )

        memories = sorted(
            zip(results["ids"], results["documents"], results["metadatas"]),
            key=lambda x: x[2].get("timestamp", ""),
            reverse=True
        )[:limit]

        response = [
            {
                "id":       mem_id,
                "document": doc,
                "metadata": meta
            }
            for mem_id, doc, meta in memories
        ]

        return response

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{id}", response_model=dict)
def memory_get_by_id(id: str) -> dict:
    """
    Retrieve a specific memory by its unique identifier from the ChromaDB collection.

    Args:
        id (str): The unique identifier of the memory to retrieve.

    Returns:
        dict: A dictionary containing the memory's details, including its ID, document, and metadata.

    Raises:
        HTTPException: 404 if the memory is not found, or 500 for other database query errors.
    """
    logger.info(f"📜 GET /memory/{id}")

    try:
        collection = app.config.client.get_or_create_collection(name=app.config.MEMORY_COLLECTION)

        results = collection.get(
            ids=[id],  # required field, but ignored with `where`
            include=["ids", "documents", "metadatas"]
        )

        if not results["documents"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        response = {
            "id": id,
            "document": results["documents"][0],
            "metadata": results["metadatas"][0]
        }

        return response

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{id}", response_class=Response)
def memory_delete(id: str) -> Response:
    """
    Delete a specific memory by its unique identifier from the ChromaDB collection.

    Args:
        id (str): The unique identifier of the memory to delete.

    Returns:
        Response: A 204 No Content response if the memory is successfully deleted.

    Raises:
        HTTPException: 500 for database query errors.
    """
    logger.info(f"📜 DELETE /memory/{id}")

    try:
        collection = app.config.client.get_or_create_collection(name=app.config.MEMORY_COLLECTION)

        collection.delete(
            ids=[id]
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{id}", response_model=dict)
def memory_replace(id: str, request_data: EmbeddedMemoryEntry) -> JSONResponse:
    """
    Replace an existing memory in the ChromaDB collection with a new memory.

    Args:
        id (str): The unique identifier of the memory to replace.
        request_data (MemoryRequest): The new memory data containing memory content, embedding, component, and priority.

    Returns:
        JSONResponse: A response indicating successful memory replacement with the memory ID.

    Raises:
        HTTPException: 500 for database query errors during memory replacement.
    """
    logger.info(f"🔁 PUT /memory/{id}")

    try:
        collection = app.config.client.get_or_create_collection(name=app.config.MEMORY_COLLECTION)

        # First delete the existing memory (if it exists)
        collection.delete(ids=[id])

        # Add the new memory with same ID
        collection.add(
            ids=[id],
            documents=[request_data.memory],
            embeddings=[request_data.embedding],
            metadatas=[{
                "timestamp": datetime.now().isoformat(),
                "component": request_data.component,
                "priority": request_data.priority
            }]
        )

        return JSONResponse(
            content={"message": "Memory replaced", "id": id},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{id}", response_model=dict)
def memory_patch(id: str, patch_data: dict) -> JSONResponse:
    """
    Partially update an existing memory in the ChromaDB collection.

    Args:
        id (str): The unique identifier of the memory to patch.
        patch_data (dict): A dictionary containing fields to update (memory, embedding, component, priority).

    Returns:
        JSONResponse: A response indicating successful memory patch with the memory ID.

    Raises:
        HTTPException: 404 if memory not found, 500 for database query errors during memory patching.
    """
    logger.info(f"🩹 PATCH /memory/{id}")

    try:
        collection = app.config.client.get_or_create_collection(name=app.config.MEMORY_COLLECTION)

        # Retrieve current memory state
        existing = collection.get(ids=[id], include=["documents", "metadatas", "embeddings"])

        if not existing["documents"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        # Pull existing fields
        current_doc = existing["documents"][0]
        current_meta = existing["metadatas"][0]
        current_embedding = existing["embeddings"][0]

        # Patch document if changed
        new_doc = patch_data.get("memory", current_doc)
        new_embedding = patch_data.get("embedding", current_embedding)

        # Patch metadata
        patched_meta = {
            **current_meta,
            "component": patch_data.get("component", current_meta.get("component")),
            "priority": patch_data.get("priority", current_meta.get("priority")),
            "timestamp": datetime.now().isoformat()  # Always refresh timestamp
        }

        # Update memory with new content
        collection.update(
            ids=[id],
            documents=[new_doc],
            embeddings=[new_embedding],
            metadatas=[patched_meta]
        )

        return JSONResponse(
            content={"message": "Memory patched", "id": id},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"🛑 ERROR querying ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
