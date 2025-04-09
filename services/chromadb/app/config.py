"""
Initialize a persistent ChromaDB client with a specified storage path.

This client provides persistent storage for embeddings and metadata,
allowing data to be saved and retrieved across application sessions.

Attributes:
    client (chromadb.PersistentClient): ChromaDB client configured with a persistent storage path.
"""
from chromadb import PersistentClient
client                                  = PersistentClient(path='./shared/db/chromadb/')

# list of collections for
MEMORY_COLLECTION                       = 'memory'
SUMMARIZE_COLLECTION                    = 'summarize'
BUFFER_COLLECTION                       = 'buffer'

# embedding model name
CHROMADB_MODEL_NAME                     = "intfloat/e5-small-v2"
