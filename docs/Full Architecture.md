# 🧠 Full Architecture

## 🧭 Architectural Principles

- **Brain is the primary orchestrator.**
- **The Proxy is the only service allowed to communicate with any LLM.** Prompt scaffolding, model selection, and stream handling are owned by the Proxy.
- **Centralized logging is mandatory.** All services must emit structured debug and error logs to Graylog.
- **Semantic search is overhyped.** We use SQLite here.

## 🧠 System Architecture Overview

### 🌐 [API](Services/API.md)

Adapter layer between OpenAI-style clients (e.g., OpenWebUI) and the internal Kirishima ecosystem.

**Responsibilities:**

- Accepts incoming messages from OpenAI-compatible clients
- Distinguishes between structured task calls and standard chat
  - For example, OpenWebUI sends tasks as `### Task:` which bypass normal LLM flow
- Routes messages to Brain for processing
- Converts internal shared class models into OpenAI response format before returning

**Design Notes:**

- Does not handle any memory, context, or summarization logic
- Has no direct LLM access
- All processing is delegated to Brain and Proxy

---

### 🧠 [Brain](Services/Brain.md)

Central reasoning and memory hub. Owns memory, buffer state, and behavioral logic.

**Responsibilities:**

- Memory via **SQLite**
- Buffer & conversation state via Ledger
- Incoming job pings from Scheduler via `POST` endpoints
- Contact resolution via Contacts
- Outbound action dispatch (email, memory, messaging)
- LLM Tool Execution
- Alerts via Notifications
- Reminders via Stickynotes

---

### 📇 [Contacts](Services/Contacts.md)

**Responsibilities:**

- Central identity resolution service
- Stores contact info across platforms (e.g., iMessage ID, Discord, email)
- Supports aliases, metadata, notes
- Enables unified user reference across the stack

---

### 📇 [Discord](Services/Discord.md)

**Responsibilities:**

- Used as an alerting outgoing mechanism.
- Allows users to sign up and talk to the LLM
- Does not support speaking in servers.

---

### 📺 [Divoom](Services/Divoom.md)

**Responsibilities:**

- Controls Divoom Max display (runs outside Docker due to Bluetooth stack limitations)
- Displays emoji based on conversation tone, topic changes, TTS activity, or system events
- Exposes /send endpoint; accepts emoji input, avoiding redundant updates
- Uses pixoo library for device communication; emoji images stored locally (Twemoji format)
- Selection policy is adaptive, prioritizing meaningful feedback over noise

---

### 💬 [iMessage](Services/iMessage.md)

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

### 🪪 [Ledger](Services/Ledger.md)

**Responsibilities:**

- Maintains persistent, cross-platform conversation buffer using SQLite
- Deduplicates, syncs, and edits message logs from all platforms (e.g., Discord, iMessage)
- Supplies the most recent N messages for context in multiturn requests
- Tracks message metadata (timestamps, user ID, tool outputs) for accurate recall
- Authoritative source for conversation history and summary generation

---

### 🔁 [Proxy](Services/Proxy.md)

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

### ⏱ [Scheduler](Services/Scheduler.md)

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

### 🏠 [Smarthome](Services/Smarthome.md)

**Responsibilities:**

- Orchestrates natural language control over home automation devices
- Processes user requests to manage lighting, audio, and other smart devices
- Integrates with multiple device types, enabling unified smart home commands
- Acts as the agent’s interface to all home automation endpoints

---

### 🗒️ [Stickynotes](Services/Stickynotes.md)

**Responsibilities:**

- Manages persistent, context-aware reminders (distinct from push notifications)
- Surfaces reminders only during user interaction—never as unsolicited alerts
- Supports snoozing, recurring, and custom-trigger reminders
- Prompts user for confirmation, snooze, or deletion when surfaced
- Designed for gentle accountability—reminders wait for engagement, not urgency

---

### 📚 [Summarize](Services/Summarize.md)

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

### 🗣️ [TTS](Services/TTS.md)

**Responsibilities:**

- Provides text-to-speech audio output for agent responses
- Streams TTS using ChatterboxTTS; supports voice/model options and live playback
- Automatically enables STT (speech-to-text) for voice-driven interaction
- REST API for starting/stopping/status checks and OpenAI-compatible endpoints
- Handles voice prompt management, audio output, and STT integration (Vosk/Whisper)

---

### 📊 Logging & Monitoring

- Centralized logging via Graylog (GELF + graypy)
- Monitoring data will integrate with Prometheus/Grafana or similar in future
