# 🧠 Full Architecture

## 🧭 Architectural Principles

- **Brain is the sole orchestrator.** No service should directly invoke another without going through Brain.
- **The Proxy is the only service allowed to communicate with any LLM.** Prompt scaffolding, model selection, and stream handling are owned by the Proxy.
- **Only Brain should talk to Summarize.** Summarization requests must be routed through Brain to preserve context awareness.
- **Database operations should be routed through Brain** unless explicitly exempted. Summarize currently violates this due to performance constraints, but this is considered a temporary exception.
- **Centralized logging is mandatory.** All services must emit structured debug and error logs to Graylog. Observability is non-negotiable.

## 🧠 System Architecture Overview

### 🌐 [API](docs/Services/APIy.md)

Adapter layer between OpenAI-style clients (e.g., OpenWebUI) and the internal Kirishima ecosystem.

**Responsibilities:**

- Accepts incoming messages from OpenAI-compatible clients
- Distinguishes between structured task calls and standard chat
  - For example, OpenWebUI sends tasks as `### Task:` which bypass normal LLM flow
- Routes messages to Brain's `/messages/api` endpoint for processing
- Converts internal shared class models into OpenAI response format before returning
- Handles function output short-circuiting when Brain responds without LLM involvement

**Design Notes:**

- Does not handle any memory, context, or summarization logic
- Has no direct LLM or database access
- All processing is delegated to Brain and Proxy

---

### 🧠 [Brain](docs/Services/Brain.md)

Central reasoning and memory hub. Owns memory, buffer state, and behavioral logic.

**Responsibilities:**

- Memory via **ChromaDB**
- Buffer & conversation state via **SQLite**
- Current `mode` state in the `status` table
- Incoming job pings from Scheduler via `POST` endpoints
- Contact resolution via Contacts service
- Outbound action dispatch (email, memory, messaging)

---

### 🧬 [ChromaDB](docs/Services/ChromaDB.md)

Dedicated vector memory store for long-term semantic retrieval.

**Responsibilities:**

- Stores and retrieves embedded memory chunks and summaries
- Used exclusively by **Brain** and **Summarize Service**
- ❌ No other component accesses ChromaDB directly
- Currently SQLite backed, converting to DuckDB due to stability issues.

---

### 📇 [Contacts](docs/Services/Contacts.md)

**Responsibilities:**

- Central identity resolution service
- Stores contact info across platforms (e.g., iMessage ID, Discord, email)
- Supports aliases, metadata, notes
- Enables unified user reference across the stack

---

### 💬 [iMessage](docs/Services/iMessage.md)

BlueBubbles-powered microservice for iMessage integration.

**Responsibilities:**

- Webhook receiver for incoming iMessages.
- Sends messages via BlueBubbles HTTP API.
- Passes incoming messages to Brain.
- Origin-aware for downstream context usage.

**Design Notes:**

- Integrated into the push-notification framework.
- Does not handle summarization or memory directly.
- Relies on Brain for routing, summarization requests, and logging.

---

### 🔁 [Proxy](docs/Services/Proxy.md)

This service handles all LLM interaction. No other service may call the LLM.

**Responsibilities:**

- Exposes endpoints like `/from/{platform}` and `/to/{platform}` to handle inbound and outbound platform-specific routing.
- Centralizes prompt scaffolding logic.
- All LLM requests (including summarization) must pass through this service.

**Core Principle:**

- This service acts as the exclusive LLM boundary.

Acts as a bridge between OpenAI-compatible clients and the Ollama backend.

**Contacts Brain to:**

- Store message buffer (incoming & outgoing messages)
- Retrieve conversation summaries for prompt injection
- Handle `create_memory()` / `delete_memory()` function calls
- List current memory entries for prompt construction
- Get/set current mode (`default`, `work`, `nsfw`)
- Schedule tasks via Brain endpoints (which relay to Scheduler)

---

### ⏱ [Scheduler](docs/Services/Scheduler.md)

Handles timed tasks using APScheduler (v3.x).

**Responsibilities:**

- Runs scheduled jobs (e.g., summarization, future alerts)
- Exposes REST API for job management:
  - `POST /jobs`, `GET /jobs`, `DELETE /jobs/{id}`
  - `POST /jobs/{id}/pause`, `POST /jobs/{id}/resume`
- Persists jobs to SQLite (DB-backed APScheduler)

**Core Principle:**  

- Scheduler performs no logic—just triggers Brain based on time
- Passes metadata to Brain, which performs the action

---

### 📚 [Summarize](docs/Services/Summarize.md)

Abstraction layer over ChromaDB for managing:

- Long-form summaries (email, dense messages)
- Short-form buffers (SMS, Discord, etc.)

**Responsibilities:**

- Accepts buffer entries via `/buffer`
- Stores user summaries via `/summary`
- Summarizes per-user grouped content via `POST /summarize_buffers`
- Exposes `/context/{user_id}` for merged view

**Workflow:**

1. Collect buffer messages per user
2. Send to local LLM via Proxy
3. Store via `/summary`
4. Clear buffer for that user

---

### 📊 Logging & Monitoring

- Centralized logging via Graylog (GELF + graypy)
- Monitoring data will integrate with Prometheus/Grafana or similar in future

### 📘 Reference

- See [Ports and Endpoints](docs/Ports%20Band%20BEndpoints.md) for live FastAPI service locations
- [Project Overview](docs/Project%20BOverview.md) provides a full onboarding reference
