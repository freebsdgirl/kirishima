
# 🔁 API

## Purpose
Serves as the bridge between OpenAI-compatible clients and the internal reasoning system ([[Brain]] via Ollama). It exposes standardized `/chat/completions` and `/completions` endpoints, wraps function-calling logic, and manages prompt construction, context injection, memory access, and user interaction scaffolding.

## Port
4200

## Endpoints

### Core Endpoints
- `POST /chat/completions` – Stateful, multi-turn conversations with full memory and buffer context (primary user interface)
- `POST /completions` – Stateless one-shot completion (used by subsystems or integrations)

### Function Dispatch
- `POST /function` – Receives function-style requests and routes them through `functions.py`

### Supporting
- `POST /scheduler` – Job registration and handling (relays to Brain/Scheduler)
- `POST /upload` – Handle file uploads
- `POST /embeddings` – Embedding generation (Ollama-wrapped)
- `POST /chromadb_search` – Semantic memory search

## Function Modules

- `functions.py` – Master dispatcher for system-defined callable logic
- `memory_functions.py` – Handles `create_memory` and `delete_memory`
- `mode.py` – Get/set mode (⚠️ bug: currently doesn't contact Brain)
- `buffer.py` – Interface for short-term conversational state
- `system.py` – Returns platform and instance metadata

## Prompt Logic

- `generate.py` – Constructs prompt payloads for Ollama
- `format_memory.py` – Prepares long-term memory segments
- `prompts.py` – Prompt templates by type
- `get_model.py` / `list_models.py` – Model management

## Integrations

- ✅ **[[ChromaDB]]** – via Brain (retrieves memory and buffer state)
- ✅ **[[Scheduler]]** – job queueing via Brain interface
- ✅ **MyAnimeList (MAL)** – `mal_show_synopsis.py` provides synopsis lookups via `functions.py`
  - ⚠️ Currently lives inside the API Intermediary, but may be moved to a separate enrichment microservice for broader reuse

## Responsibilities
- Normalize OpenAI-compatible interface
- Route requests to [[Brain]] for memory, summaries, and metadata
- Handle mode state (partial)
- Perform inline function resolution (`create_memory`, `show_synopsis`, etc.)
- Facilitate subsystem interactions in a centralized, schema-consistent way

## Known Issues
- Mode switching via `mode.py` is not synced with Brain (fix planned)
- Some endpoints (e.g., completions) previously outdated, now corrected
- Function routing may need validation against memory state tracking logic

## External Dependencies
- [[Brain]] (via HTTP)
- Ollama (local LLM backend)
- [[ChromaDB]] (via Brain)
- [[Scheduler]] (via Brain)
