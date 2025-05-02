# 📇 ChromaDB

## Purpose

ChromaDB provides an HTTP API for storing, retrieving, updating, and searching vector-encoded memory entries. It acts as the semantic memory and summary backend for the Kirishima system, abstracting direct vector database operations for services like Brain.

## How It Works

- Built with FastAPI, the service initializes the app, adds request body caching middleware, and registers routers for memory management, summary management, and search.
- All endpoints operate on a single logical collection of memory  and summary entries, each with document text, embedding, and metadata (component, mode, priority, timestamp).
- Embeddings are generated as needed for new entries and semantic search queries.
- The service supports exact-match and semantic search, as well as CRUD operations on memory entries.
- There are no endpoints for buffer or summary management in the current codebase.
- Tracing is supported if enabled in the configuration.

## Port

4206

## Main Endpoints

### Memory (`/memory`)

- `POST /memory` – Add a memory entry (document + embedding + metadata)
- `GET /memory` – List memory entries, with optional filters
- `GET /memory/id/{memory_id}` – Retrieve a specific memory by ID
- `PUT /memory/{memory_id}` – Replace a memory entry by ID
- `PATCH /memory/{memory_id}` – Partially update a memory entry by ID
- `DELETE /memory/{memory_id}` – Delete a memory entry by ID
- `GET /memory/search` – Exact-match search on memory text
- `GET /memory/semantic` – Semantic search on memory content and metadata

### Embedding

- `POST /embedding` – Generate an embedding for a given input

### Summary (`/summary`)

- `POST /summary` – Add a summary entry
- `GET /summary` – List summary entries
- `DELETE /summary/{summary_id}` – Delete a summary entry by ID

### System & Docs

- `GET /ping` – Health check
- `GET /__list_routes__` – List all registered API routes
- `GET /docs/export` – Export internal documentation for the ChromaDB service

## Responsibilities

- Store and manage vector-encoded memory entries with metadata
- Provide fast search for relevant context (recent and semantically similar)
- Normalize and validate embedding inputs
- Expose a simple, consistent API for use by Brain and other services

## Internal Details

- Uses dependency injection for the ChromaDB collection
- Embeddings are generated using a shared embedding utility
- All endpoints validate input and handle errors with structured responses
- Middleware is used for request body caching
- Tracing is enabled if configured

## External Dependencies

- FastAPI
- ChromaDB (as a Python library)
- Sentence-transformers (for embedding generation)

## Consuming Services

- **Brain**: Reads/writes memory entries
