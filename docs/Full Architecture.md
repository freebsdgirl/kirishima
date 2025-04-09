
# 🧠 System Architecture Overview

---

## 🧭 Architectural Principles

- **Brain is the sole orchestrator.** No service should directly invoke another without going through Brain.
- **The Proxy is the only service allowed to communicate with any LLM.** Prompt scaffolding, model selection, and stream handling are owned by the Proxy.
- **Only Brain should talk to Summarize.** Summarization requests must be routed through Brain to preserve context awareness.
- **Database operations should be routed through Brain** unless explicitly exempted. Summarize currently violates this due to performance constraints, but this is considered a temporary exception.
- **Centralized logging is mandatory.** All services must emit structured debug and error logs to Graylog. Observability is non-negotiable.

---

# 🧠 System Architecture Overview

---


## 🔁 [[Proxy]]

Formerly known as `llm-proxy`, this service handles all LLM interaction. No other service may call an LLM.

**Responsibilities:**
- Exposes endpoints like `/from/{platform}` and `/to/{platform}` to handle inbound and outbound platform-specific routing.
- Will eventually centralize prompt scaffolding logic.
- All LLM requests (including summarization) must pass through this service.

**Core Principle:**
- This service acts as the exclusive LLM boundary.


Acts as a bridge between OpenAI-compatible clients and the Ollama backend.

**Flow:**  
`OpenAI client → API Intermediary → Ollama`

**Responsibilities:**
- Contacts **Brain** to:
  - ✅ Store message buffer (incoming & outgoing messages)
  - ✅ Retrieve conversation summaries for prompt injection
  - ✅ Handle `create_memory()` / `delete_memory()` function calls
  - ✅ List current memory entries for prompt construction
  - ✅ Get/set current mode (`default`, `work`, `nsfw`)
  - 🔄 Schedule tasks via Brain endpoints (which relay to Scheduler)

**Endpoints:**
- `/chat/completions` – Full conversational flow (multi-turn, memory-aware)
- `/completions` – One-shot, stateless completions  
  ✅ **Fixed and working**

**Known Issues:**
- ⚠️ `change_mode()` only updates a local variable and does not contact Brain. This is pending a fix.

---

## 🧠 [[Brain]]

Central reasoning and memory hub. Owns memory, buffer state, and behavioral logic.

**Responsibilities:**
- ✅ Memory via **ChromaDB**
- ✅ Buffer & conversation state via **SQLite**
- ✅ Current `mode` state in the `status` table
- ✅ Incoming job pings from Scheduler via `POST` endpoints
- ✅ Contact resolution via Contacts service
- 🔧 Outbound action dispatch (email, memory, messaging)

---

## ⏱ [[Scheduler]]

Handles timed tasks using APScheduler (v3.x).

**Responsibilities:**
- ✅ Runs scheduled jobs (e.g., summarization, future alerts)
- ✅ Exposes REST API for job management:
  - `POST /jobs`, `GET /jobs`, `DELETE /jobs/{id}`
  - `POST /jobs/{id}/pause`, `POST /jobs/{id}/resume`
- ✅ Persists jobs to SQLite (DB-backed APScheduler)

**Core Principle:**  
- Scheduler performs no logic—just triggers Brain based on time
- Passes metadata to Brain, which performs the action

---

## 🧬 [[ChromaDB]]

Dedicated vector memory store for long-term semantic retrieval.

**Responsibilities:**
- Stores and retrieves embedded memory chunks and summaries
- Used exclusively by **Brain** and **Summarize Service**
- ❌ No other component accesses ChromaDB directly

---

## 📚 [[Summarize]]

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
2. Send to local LLM (`http://localhost:11434/api/generate`)
3. Store via `/summary`
4. Clear buffer for that user

---

## 📇 [[Contacts]]

**Responsibilities:**
- Central identity resolution service
- Stores contact info across platforms (e.g., iMessage ID, Discord, email)
- Supports aliases, metadata, notes
- Enables unified user reference across the stack

**Endpoints:**
- `POST /contact` – Create contact
- `GET /contact/{id}` – Retrieve by ID
- `GET /contact` – List/search contacts
- `PATCH /contact/{id}` – Partial update
- `DELETE /contact/{id}` – Delete contact

---


## 💬 [[iMessage]] 

BlueBubbles-powered microservice for iMessage integration.

**Responsibilities:**
- Webhook receiver for incoming iMessages.
- Sends messages via BlueBubbles HTTP API.
- Passes incoming messages to Brain with `platform=iMessage` tag.
- Origin-aware for downstream context usage.

**Design Notes:**
- Integrated into the push-notification framework.
- Does not handle summarization or memory directly.
- Relies on Brain for routing, summarization requests, and logging.


## 📊 Logging & Monitoring

- ✅ Centralized logging via Graylog (GELF + graypy)
- 🧠 Monitoring data will integrate with Prometheus/Grafana or similar in future

---

## 📘 Reference

- See `ports_and_endpoints.md` for live FastAPI service locations
- `kirishima_project_overview.md` provides a full onboarding reference

---

