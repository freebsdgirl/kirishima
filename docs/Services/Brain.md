# 🧠 Brain

## Purpose

Brain is the central orchestrator of the Kirishima architecture. It coordinates all inter-service logic including contact resolution, summarization, memory embedding, reply generation, and system status management. No other service is permitted to call external endpoints directly—Brain mediates all LLM access, summaries, memory reads/writes, and platform-specific communication.

## Port

4207

## Endpoints Overview

This service exposes a wide array of endpoints via routers for:

- Memory management (`/memory`, `/memory/{id}`)
- Rolling buffer and ephemeral summarization (`/buffer/conversation`)
- Scheduler job intake and callbacks (`/scheduler`)
- System mode handling (`/status/mode`)
- Message ingestion and reply generation (`/message/incoming`)
- OpenAPI export for contract metadata (`/docs/export`)

## 🧠 Brain Service – Endpoint Reference

This is a complete list of all public endpoints exposed by the Brain microservice, grouped by functionality.

### 📥 Message Routing

#### `POST /message/incoming`

Process a user message:

- Resolves contact identity
- Retrieves summarization context
- Buffers message
- Fetches memories (if self)
- Calls reply endpoint via Proxy
- Buffers the generated reply
Returns: user_id, buffer_entry_id, context, reply

### 🧠 Memory Management

#### `POST /memory`

Create a new memory with embedding.

- Requires: `memory`, `component`, `priority`
- Embeds using sentence transformer
- Forwards to ChromaDB

#### `GET /memory`

List recent memories for a specific component.

- Params: `component`, `limit`

#### `GET /memory/{id}`

Retrieve a specific memory by ID.

#### `DELETE /memory/{id}`

Delete a memory by ID.

#### `PUT /memory/{id}`

Replace an entire memory (new text, component, priority).

#### `PATCH /memory/{id}`

Partially update a memory (e.g., just text or priority).

#### `POST /memory/search/id`

Return the ID of a memory that matches the input string.

### 💾 Rolling Buffer

#### `POST /buffer/conversation`

Insert a single conversation message into the SQLite buffer.

#### `GET /buffer/conversation`

Retrieve all stored ephemeral summaries from the SQLite `summaries` table.

### 📅 Scheduler Integration

#### `POST /scheduler/job`

Schedule a new job in the external scheduler.

- Fields: `id`, `external_url`, `trigger`, `run_date`, `interval_minutes`, `metadata`

#### `GET /scheduler/job`

List all currently scheduled jobs.

#### `DELETE /scheduler/job/{job_id}`

Delete a scheduled job by ID.

#### `POST /scheduler/callback`

Callback from Scheduler. Executes function from `metadata.function`.

### 🧭 System Mode

#### `GET /status/mode`

Returns current system mode (e.g., “chat”, “dev”, “proxy_default”).

#### `POST /status/mode/{mode}`

Sets the system mode.

### 📑 Internal Docs

#### `GET /docs/export`

Returns metadata about all endpoints and service version (git hash).

## Functional Modules

### 📚 Memory (`memory.py`)

- Embeds and stores new memories in ChromaDB
- Provides search, CRUD, and partial updates
- Uses `intfloat/e5-small-v2` sentence transformer for embedding generation

### 💬 Messages (`message.py`)

- Handles all incoming messages
- Steps:
  1. Resolves contact identity via Contacts service
  2. Retrieves context from Summarize
  3. Buffers the message
  4. Selects reply endpoint (`/from/imessage` or default)
  5. Calls Proxy for reply generation
  6. Buffers the reply message
- Optional: Fetches memories if the sender is the main user

### 🔁 Buffer (`buffer.py`)

- Stores messages in a rolling buffer SQLite DB
- Also reads summaries from the `summaries` table
- Used by Summarize for ephemeral context summarization

### 📅 Scheduler (`jobscheduler.py`)

- Accepts job definitions to run external summarization or trigger functions
- Callback executes registered functions like `check_and_summarize`
- All scheduler commands routed to an external Scheduler service

### 📈 Summarize Interface (`summarize.py`)

- Periodically triggered to summarize rolling buffer contents
- Summarizes in real-time if thresholds are met
- Performs meta-summarization in three stages (1 → 2 → 3)
- Writes directly to SQLite and uses timestamp guards for rate limiting

### 📊 Status (`status.py`)

- Tracks current system mode in SQLite (`status.db`)
- Used to adapt memory component selection or reply behavior

### 📜 Docs (`docs.py`)

- Exposes `/docs/export` with current route contracts and git revision

## Configuration Highlights

Set in `brain/config.py`:

- `BUFFER_SERVICE_URL`, `CONTACTS_SERVICE_URL`, `SUMMARIZE_BUFFER_URL`, etc.
- Summarization thresholds: `SUMMARIZE_THRESHOLD_ACTIVE`, `DENSITY_THRESHOLD_LINES`
- Summary rate-limiting: `MIN_SUMMARY_INTERVAL_SECONDS`
- Special memory routing for `RANDI_USER_ID` messages
- `IMESSAGE_REPLY_ENDPOINT` and fallback `DEFAULT_REPLY_ENDPOINT`

## Notes

- All inter-service communication is over HTTP
- Brain does not store memory or summaries locally except for buffers
- Summarization and meta-summarization stages are controlled by SQLite, not background workers
- All logic is linear and blocking unless offloaded to the Scheduler
