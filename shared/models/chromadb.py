"""
This module defines data models for managing memory entries in the ChromaDB collection.
Classes:
    MemoryEntry:
            - memory (str): The content of the memory to be stored.
            - component (str): The component associated with the memory.
            - mode (str): The mode of the memory (e.g., "nsfw", "default").
            - priority (float): The priority level of the memory.
            - embedding (list): The vector embedding representation of the memory.
    MemoryMetadata:
            - timestamp (str): The UTC timestamp when the memory was created, with 'Z' indicating UTC timezone.
            - priority (float): The priority level of the memory, ranging from 0 (lowest) to 1 (highest).
            - component (str): The component that created the memory.
            - mode (str): The mode of the memory, defaulting to 'default' with options like 'nsfw'.
    MemoryEntryFull:
        Represents a complete memory entry with its metadata and unique identifier.
            - id (str): Unique identifier for the memory.
            - memory (str): The content of the memory.
            - embedding (List[float]): The vector embedding of the memory.
            - metadata (MemoryMetadata): Metadata associated with the memory.
    MemoryView:
        Represents a view of a memory entry, including its distance from a query vector.
            - id (str): Unique identifier for the memory.
            - memory (str): The content of the memory.
            - embedding (List[float]): The vector embedding of the memory.
            - metadata (MemoryMetadata): Metadata associated with the memory.
            - distance (Optional[float]): Distance of the memory from the query vector.
    MemoryQuery:
        Represents a query for filtering memory entries based on specific criteria.
            - component (Optional[str]): Filter by component.
            - mode (Optional[str]): Filter by mode.
            - priority (Optional[float]): Filter by priority.
    MemoryPatch:
        Represents a patch request for updating memory entries.
            - memory (Optional[str]): The content of the memory.
            - mode (Optional[str]): Mode of the memory (e.g., 'nsfw', 'default').
            - component (Optional[str]): Component that created the memory.
            - priority (Optional[float]): Priority level of the memory.
            - embedding (Optional[List[float]]): The vector embedding of the memory.
    MemoryListQuery:
        Represents a query for listing memory entries based on component and mode.
            - component (str): Required filter to select memories by their creating component.
            - mode (Optional[str]): Optional filter to select memories by their mode (e.g., 'nsfw', 'default').
    SemanticSearchQuery:
        Represents a query for performing semantic search in the ChromaDB collection.
            - search (str): The query text to perform semantic search against the collection.
            - component (Optional[str]): Optional filter to select memories by their creating component.
            - mode (Optional[str]): Optional filter to select memories by their mode (e.g., 'nsfw', 'default').
            - limit (Optional[int]): Optional maximum number of search results to return.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4


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


class MemoryMetadata(BaseModel):
    """
    Represents the metadata associated with a memory entry in the ChromaDB collection.
    
    Attributes:
        timestamp (str): The UTC timestamp when the memory was created, with 'Z' indicating UTC timezone.
        priority (float): The priority level of the memory, ranging from 0 (lowest) to 1 (highest).
        component (str): The component that created the memory.
        mode (str): The mode of the memory, defaulting to 'default' with options like 'nsfw'.
    """
    timestamp: str                      = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z", description="Timestamp when the memory was created")  
    priority: float                     = Field(..., ge=0, le=1, description="0=lowest, 1=highest")
    component: str                      = Field(..., description="Component that created the memory")
    mode: str                           = Field("default", description="Mode of the memory (e.g., 'nsfw', 'default')")


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