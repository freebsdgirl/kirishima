# Standalone ChromaDB embedding cleanup script
import os
import chromadb
from chromadb.utils.embedding_functions import EmbeddingFunction
from sentence_transformers import SentenceTransformer

# --- CONFIG ---
# Path to ChromaDB persistent directory (relative to this script)
CHROMADB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../shared/db/chromadb'))
COLLECTION_NAME = 'memory'  # or use your configured collection name
EMBEDDING_MODEL = 'intfloat/e5-small-v2'

# --- Embedding function (copied from setup.py) ---
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

class E5EmbeddingFunction(EmbeddingFunction):
    def __call__(self, input):
        return embedding_model.encode(input).tolist()

# --- Main logic ---
def main():
    print(f"Opening ChromaDB at {CHROMADB_PATH}")
    client = chromadb.PersistentClient(path=CHROMADB_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=E5EmbeddingFunction()
    )
    print("Scanning for corrupted memory entries (empty or missing embeddings)...")
    results = collection.get(include=["embeddings", "documents", "metadatas"])
    ids = results.get("ids", [])
    embeddings = results.get("embeddings", [])
    to_delete = []
    for idx, emb in enumerate(embeddings):
        if emb is None or len(emb) == 0:
            to_delete.append(ids[idx])
    if not to_delete:
        print("No corrupted entries found.")
        return
    print(f"Found {len(to_delete)} corrupted entries. Deleting...")
    collection.delete(ids=to_delete)
    print("Deleted the following IDs:")
    for _id in to_delete:
        print(_id)

if __name__ == "__main__":
    main()