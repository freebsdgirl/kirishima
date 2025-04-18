"""
This module sets up a ChromaDB collection with a custom embedding function using a pre-loaded 
SentenceTransformer model for generating dense vector embeddings.
Classes:
    E5EmbeddingFunction: A custom embedding function for ChromaDB that uses the E5 embedding model 
    to convert input text into vector embeddings.
Functions:
    collection() -> chromadb.Collection: Initializes and returns a ChromaDB collection with 
    persistent storage and the custom E5 embedding function.
Dependencies:
    - app.config: Contains configuration settings such as the embedding model, ChromaDB path, 
      and memory collection name.
    - chromadb: The ChromaDB library for managing collections and embeddings.
    - chromadb.utils.embedding_functions.EmbeddingFunction: Base class for custom embedding functions.
    - sentence_transformers.SentenceTransformer: Library for generating text embeddings using 
      pre-trained models.
"""
import app.config

import chromadb

from chromadb.utils.embedding_functions import EmbeddingFunction
from sentence_transformers import SentenceTransformer


embedding_model = SentenceTransformer(app.config.EMBEDDING_MODEL)


class E5EmbeddingFunction(EmbeddingFunction):
    """
    A custom embedding function for ChromaDB that uses the pre-loaded E5 embedding model.

    Converts input text into dense vector embeddings using the SentenceTransformer model,
    compatible with ChromaDB's embedding function interface.

    Args:
        input (list): A list of text inputs to be encoded into vector embeddings.

    Returns:
        list: A list of vector embeddings corresponding to the input texts.
    """
    def __call__(self, input):
        return embedding_model.encode(input).tolist()


def collection() -> chromadb.Collection:
    """
    Initializes and returns a ChromaDB collection with persistent storage and custom E5 embeddings.
    
    Returns:
        chromadb.Collection: A ChromaDB collection configured with the specified embedding function.
    """
    # Initialize ChromaDB with persistent storage
    client = app.config.client

    # Create collection with custom embeddings
    collection = client.get_or_create_collection(
        name=app.config.MEMORY_COLLECTION,
        embedding_function=E5EmbeddingFunction()  # Proper class-based embedding function
    )

    return collection
