# 📇 ChromaDB

## Purpose

Provides an HTTP API layer over a persistent ChromaDB instance for handling:

- Semantic memory
- Short-form buffer entries
- Summarized conversation data

This microservice abstracts away direct vector database operations for the rest of the Kirishima system, allowing services like Brain and Summarize to store and retrieve embeddings in a modular, standardized way.

## Port

4206

## Endpoints

### Memory (`/memory`)

- `POST /memory` – Add memory (document + embedding + metadata)
- `GET /memory` – List recent memory entries by component
- `GET /memory/{id}` – Retrieve specific memory
- `POST /memory/search/id` – Search memory IDs by content
- `PUT`, `PATCH`, `DELETE /memory/{id}` – Update or remove memory

### Summary (`/summarize`)

- `POST /summarize` – Store a summary entry
- `GET /summarize/{id}` – Retrieve summary by ID
- `GET /summarize/user/{user_id}` – Retrieve summaries for a user
- `GET /summarize/search` – Semantic + metadata search
- `DELETE /summarize/{id}` – Delete summary by ID

### Buffer (`/buffer`)

- `POST /buffer` – Add a short-form buffer entry
- `GET /buffer` – Retrieve all buffer entries
- `GET /buffer/{user_id}` – Get buffer by user
- `DELETE /buffer/{user_id}` – Clear buffer by user

## Responsibilities

- Store vector-encoded memories with metadata (timestamp, component, priority)
- Store per-message short-form inputs to support scheduled summarization
- Store generated summaries in a dedicated summary collection
- Provide fast search for relevant context (recent + semantically similar)
- Normalize and validate embedding inputs
- Keep all data persistent across restarts via `PersistentClient`

## Collections

- `memory`: Long-term memory entries used by Brain
- `buffer`: Short-form message buffer for user conversations
- `summarize`: Abstracted semantic summaries per platform/user

## Internal Details

- Uses SentenceTransformer for embeddings (`intfloat/e5-small-v2`)
- All endpoints generate or validate embeddings before storage
- Implements semantic search with distance + recency scoring
- Uses `chroma.config` to centralize collection names and model selection

## External Dependencies

- `sentence-transformers`
- FastAPI
- ChromaDB (as a Python lib, not a separate service)

## Consuming Services

- **Brain**: Reads/writes memory, buffer, and summaries
- **Summarize**: Reads/writes buffer and summaries
