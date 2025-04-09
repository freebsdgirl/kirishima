"""
This module provides functionality for generating dense vector embeddings from text inputs 
using a pre-configured SentenceTransformer model. It includes a Pydantic model for validating 
embedding requests and a function to process the requests.
Classes:
    EmbeddingRequest: A Pydantic model representing a request for generating a text embedding.
Functions:
    get_embedding(request: EmbeddingRequest) -> list: Generates a dense vector embedding 
    for the given text input using the SentenceTransformer model.
    model (SentenceTransformer): A pre-configured SentenceTransformer model initialized 
    with the model name specified in the chroma configuration.
"""

import app.config

from sentence_transformers import SentenceTransformer
from pydantic import BaseModel


"""
Initialize a SentenceTransformer model for generating text embeddings.

Uses the model specified in the configuration to convert text into dense vector representations
that can be used for semantic similarity and embedding tasks.

Attributes:
    model (SentenceTransformer): Pre-configured transformer model for generating text embeddings.
"""
model = SentenceTransformer(app.config.CHROMADB_MODEL_NAME)


class EmbeddingRequest(BaseModel):
    """
    Represents a request for generating a text embedding.
    
    Attributes:
        input (str): The text input to be converted into a dense vector representation.
    """
    input: str


def get_embedding(request: EmbeddingRequest) -> list:
    """
    Generate a dense vector embedding for the given text input.
    
    Args:
        request (EmbeddingRequest): The text input to be converted into a vector representation.
    
    Returns:
        list: A list of float values representing the text embedding.
    """
    return model.encode(request.input).tolist()
