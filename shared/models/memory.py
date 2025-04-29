"""
This module defines Pydantic models for managing and querying memory entries in a ChromaDB collection.
Models included:
- MemorySearch: Model for searching memory entries by text and optional filters such as component, mode, priority, and result limit.
- SemanticSearchQuery: Model for performing semantic search queries with optional component, mode, and result limit filters.
- MemoryListQuery: Model for listing memory entries filtered by component (required), mode, and result limit.
- MemoryQuery: Model for filtering memory entries by optional component, mode, and priority.
- MemoryPatch: Model for partial updates to memory entries, allowing selective updates to content, mode, component, priority, and embedding.
- MemoryMetadata: Model representing metadata associated with a memory entry, including timestamp, priority, component, and mode.
- MemoryView: Model representing a view of a memory entry, including its unique identifier, content, embedding, metadata, and optional query distance.
- MemoryEntry: Model for creating a new memory entry, including content, component, mode, priority, and optional embedding.
- MemoryEntryFull: Model representing a complete memory entry with a unique identifier, content, embedding, and metadata.
Each model includes example data for schema generation and documentation purposes.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import uuid4
from datetime import datetime


class MemorySearch(BaseModel):
    text: str                           = Field(..., description="Text to search in memory")
    component: Optional[str]            = Field(None, description="Filter by component")
    mode: Optional[str]                 = Field(None, description="Filter by mode")
    priority: Optional[float]           = Field(None, ge=0, le=1, description="Filter by priority (0-1 range)")
    limit: Optional[int]                = Field(None, ge=1, description="Max number of results to return")
 
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "What is the weather like today?",
                    "component": "weather",
                    "mode": "query",
                    "priority": 0.8,
                    "limit": 5
                },
                {
                    "text": "Tell me about the latest news.",
                    "component": "news",
                    "mode": "summary",
                    "priority": 0.9,
                    "limit": 10
                }
            ]
        }
    }


class SemanticSearchQuery(BaseModel):
    """
    Represents a query model for performing semantic search in a ChromaDB collection.
    
    Attributes:
        search (str): The query text to perform semantic search against the collection.
        component (Optional[str]): Optional filter to select memories by their creating component.
        mode (Optional[str]): Optional filter to select memories by their mode (e.g., 'nsfw', 'default').
        limit (Optional[int]): Optional maximum number of search results to return.
    """
    search: str                         = Field(..., description="Query text for semantic search")
    component: Optional[str]            = Field(None, description="Filter by component")
    mode: Optional[str]                 = Field(None, description="Filter by mode")
    limit: Optional[int]                = Field(None, description="Max number of results")  

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "search": "What is the weather like today?",
                    "component": "weather",
                    "mode": "query",
                    "limit": 5
                },
                {
                    "search": "Tell me about the latest news.",
                    "component": "news",
                    "mode": "summary",
                    "limit": 10
                }
            ]
        }
    }


class MemoryListQuery(BaseModel):
    """
    Represents a query model for filtering a list of memory entries in a ChromaDB collection.
    
    Attributes:
        component (str): Required filter to select memories by their creating component.
        mode (Optional[str]): Optional filter to select memories by their mode (e.g., 'nsfw', 'default').
        limit (Optional[int]): Optional maximum number of memory entries to return.
    """
    component: str                      = Field(..., description="Filter by component")
    mode: Optional[str]                 = Field(None, description="Filter by mode")
    limit: Optional[int]                = Field(None, description="Max number of results")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "component": "weather",
                    "mode": "query",
                    "limit": 5
                },
                {
                    "component": "news",
                    "mode": "summary",
                    "limit": 10
                }
            ]
        }
    }


class MemoryQuery(BaseModel):
    """
    Represents a query model for filtering memory entries in a ChromaDB collection.
    
    Attributes:
        component (Optional[str]): Optional filter to select memories by their creating component.
        mode (Optional[str]): Optional filter to select memories by their mode (e.g., 'nsfw', 'default').
        priority (Optional[float]): Optional filter to select memories within a specific priority range (0-1).
    """
    component: Optional[str]            = Field(None, description="Filter by component")
    mode:      Optional[str]            = Field(None, description="Filter by mode")
    priority:  Optional[float]          = Field(None, ge=0, le=1, description="Filter by priority")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "component": "weather",
                    "mode": "query",
                    "priority": 0.8
                },
                {
                    "component": "news",
                    "mode": "summary",
                    "priority": 0.9
                }
            ]
        }
    }


class MemoryPatch(BaseModel):
    """
    Represents a partial update model for memory entries in a ChromaDB collection.
    
    Allows selective updating of memory attributes such as content, mode, component, 
    priority, and embedding. All fields are optional, enabling flexible partial updates 
    to existing memory entries.
    
    Attributes:
        memory (Optional[str]): Updated textual content of the memory.
        mode (Optional[str]): Updated mode of the memory (e.g., 'nsfw', 'default').
        component (Optional[str]): Updated component that created the memory.
        priority (Optional[float]): Updated priority level, ranging from 0 (lowest) to 1 (highest).
        embedding (Optional[List[float]]): Updated vector embedding of the memory.
    """
    memory:    Optional[str]            = Field(None, description="The content of the memory")
    mode:      Optional[str]            = Field(None, description="Mode of the memory (e.g., 'nsfw', 'default')")
    component: Optional[str]            = Field(None, description="Component that created the memory")
    priority:  Optional[float]          = Field(None, ge=0, le=1, description="0=lowest, 1=highest")
    embedding: Optional[List[float]]    = Field(None, min_items=1, description="The vector embedding of the memory")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memory": "Updated memory content",
                    "mode": "default",
                    "component": "weather",
                    "priority": 0.8,
                    "embedding": [0.1, 0.2, 0.3]
                },
                {
                    "memory": "Another updated memory content",
                    "mode": "nsfw",
                    "component": "news",
                    "priority": 0.9
                }
            ]
        }
    }


class MemoryMetadata(BaseModel):
    """
    Represents the metadata associated with a memory entry in the ChromaDB collection.
    
    Attributes:
        timestamp (str): The UTC timestamp when the memory was created, with 'Z' indicating UTC timezone.
        priority (float): The priority level of the memory, ranging from 0 (lowest) to 1 (highest).
        component (str): The component that created the memory.
        mode (str): The mode of the memory, defaulting to 'default' with options like 'nsfw'.
    """
    timestamp: str                      = Field(default_factory=lambda: datetime.now().isoformat() + "Z", description="Timestamp when the memory was created")  
    priority: float                     = Field(..., ge=0, le=1, description="0=lowest, 1=highest")
    component: str                      = Field(..., description="Component that created the memory")
    mode: str                           = Field("default", description="Mode of the memory (e.g., 'nsfw', 'default')")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2023-10-01T12:00:00Z",
                    "priority": 0.8,
                    "component": "weather",
                    "mode": "default"
                },
                {
                    "timestamp": "2023-10-01T12:00:00Z",
                    "priority": 0.9,
                    "component": "news",
                    "mode": "nsfw"
                }
            ]
        }
    }


class MemoryView(BaseModel):
    """
    Represents a view of a memory entry retrieved from a ChromaDB collection, including its unique identifier, content, embedding, metadata, and query distance.
    
    Attributes:
        id (str): A unique identifier for the memory entry.
        memory (str): The textual content of the memory.
        embedding (List[float]): A vector representation of the memory, with at least one element.
        metadata (MemoryMetadata): Detailed metadata associated with the memory entry.
        distance (Optional[float]): The distance of the memory from the query vector, used in similarity search.
    """
    id: str                             = Field(..., description="Unique identifier for the memory")
    memory: str                         = Field(..., description="The content of the memory")
    embedding: List[float]              = Field([], min_items=1, description="The vector embedding of the memory")
    metadata: MemoryMetadata            = Field(..., description="Metadata associated with the memory")
    distance: Optional[float]           = Field(0, description="Distance of the memory from the query vector")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": str(uuid4()),
                    "memory": "Sample memory content",
                    "embedding": [0.1, 0.2, 0.3],
                    "metadata": {
                        "timestamp": "2023-10-01T12:00:00Z",
                        "priority": 0.8,
                        "component": "weather",
                        "mode": "default"
                    },
                    "distance": 0.5
                },
                {
                    "id": str(uuid4()),
                    "memory": "Another sample memory content",
                    "embedding": [0.4, 0.5, 0.6],
                    "metadata": {
                        "timestamp": "2023-10-01T12:00:00Z",
                        "priority": 0.9,
                        "component": "news",
                        "mode": "nsfw"
                    }
                }
            ]
        }
    }


class MemoryEntry(BaseModel):
    """
    Represents a request for adding a memory to the ChromaDB collection.
    
    Attributes:
        memory (str): The content of the memory to be stored.
        component (str): The component associated with the memory.
        mode (str): The mode of the memory (e.g., "nsfw", "default").
        priority (float): The priority level of the memory.
        embedding (list): The vector embedding representation of the memory.
    """
    memory: str                     = Field(..., description="The content of the memory")
    component: str                  = Field(..., description="Component that created the memory")
    mode: str                       = Field("default", description="Mode of the memory (e.g., 'nsfw', 'default')")
    priority: float                 = Field(0.5, ge=0, le=1, description="0=lowest, 1=highest")
    embedding: list                 = Field(None, description="The vector embedding of the memory")  # Optional field for embedding

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memory": "Sample memory content",
                    "component": "weather",
                    "mode": "default",
                    "priority": 0.8,
                    "embedding": [0.1, 0.2, 0.3]
                },
                {
                    "memory": "Another sample memory content",
                    "component": "news",
                    "mode": "nsfw",
                    "priority": 0.9
                }
            ]
        }
    }


class MemoryEntryFull(BaseModel):
    """
    Represents a complete memory entry with a unique identifier, content, embedding, and associated metadata.
    
    Attributes:
        id (str): A unique identifier generated using UUID, automatically assigned if not specified.
        memory (str): The textual content of the memory.
        embedding (List[float]): A vector representation of the memory, requiring at least one element.
        metadata (MemoryMetadata): Detailed metadata associated with the memory entry.
    """
    id: str                             = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the memory")
    memory: str                         = Field(..., description="The content of the memory")
    embedding: List[float]              = Field(..., min_items=1, description="The vector embedding of the memory") 
    metadata: MemoryMetadata            = Field(..., description="Metadata associated with the memory")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": str(uuid4()),
                    "memory": "Sample memory content",
                    "embedding": [0.1, 0.2, 0.3],
                    "metadata": {
                        "timestamp": "2023-10-01T12:00:00Z",
                        "priority": 0.8,
                        "component": "weather",
                        "mode": "default"
                    }
                },
                {
                    "id": str(uuid4()),
                    "memory": "Another sample memory content",
                    "embedding": [0.4, 0.5, 0.6],
                    "metadata": {
                        "timestamp": "2023-10-01T12:00:00Z",
                        "priority": 0.9,
                        "component": "news",
                        "mode": "nsfw"
                    }
                }
            ]
        }
    }
