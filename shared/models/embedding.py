
"""
This module defines the `EmbeddingRequest` model for handling embedding-related requests.

Classes:
    EmbeddingRequest (BaseModel): A Pydantic model that represents a request for embedding processing.
        Attributes:
            input (str): The input string to be processed for embedding.
"""
from pydantic import BaseModel


class EmbeddingRequest(BaseModel):
    """
    A Pydantic model representing a request for text embedding.
    
    Attributes:
        input (str): The text input to be processed for generating an embedding vector.
    """
    input: str
