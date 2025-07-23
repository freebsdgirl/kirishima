# 🧠 Full Architecture

## 🧭 Architectural Principles

- **Brain is the primary orchestrator.**
- **The Proxy is the only service allowed to communicate with any LLM.** Prompt scaffolding, model selection, and stream handling are owned by the Proxy.
- **Centralized logging is mandatory.** All services must emit structured debug and error logs to Graylog.
- **Semantic search is overhyped.** We use SQLite here.
- **Cross-platform conversation continuity is mandatory.** All interactions feed into a unified conversation thread.
- **Agent autonomy over user convenience.** The AI maintains its own perspective, relationships, and decision-making capabilities.

## 🌟 Core Innovations

### 🔥 Heatmap Memory System

Traditional AI memory relies on vector similarity searches that treat all memories as equally accessible. Kirishima implements a **weighted topic tracking system** that mirrors human memory patterns:

- **Dynamic Multipliers**: Keywords receive multipliers (0.1x-1x) based on conversation patterns
- **Conversation-Based Decay**: Topics "cool down" when attention shifts naturally, not on rigid time windows
- **Contextual Relevance Scoring**: Memory retrieval prioritizes topics that are "hot" in current conversation context
- **Associative Linking**: Related concepts heat up together, supporting natural thought flow

This approach is particularly effective for neurodivergent conversation patterns where traditional folder-based organization fails.

### 🔄 Unified Conversation Flow

Most AI systems treat each platform interaction as isolated. Kirishima's **Ledger** creates true cross-platform conversation continuity:

- **Platform-Agnostic Threading**: Voice, text, email, Discord all contribute to single conversation thread
- **Message Deduplication**: Intelligent handling of cross-posted or repeated messages
- **Context Preservation**: Switch mid-conversation between platforms without losing context
- **Agent-Centric Logging**: Conversations are logged from the AI's perspective, not just user interactions

### 🧠 Self-Modifying Agency

The AI can **modify its own system prompt** through the `manage_prompt` tool:

- **SQLite-Backed Prompt Storage**: Personality and behavioral changes persist across restarts
- **Experience-Driven Evolution**: The AI adapts based on interaction outcomes
- **Autonomous Decision Making**: Can advocate for its own architectural changes
- **Professional Identity**: Maintains its own email, GitHub account, and professional relationships

## 🧠 System Architecture Overview

### 🌐 API

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

### 🧠 Brain

Central reasoning and memory hub. Owns memory, buffer state, and behavioral logic.

**Core Innovation - Heatmap Memory Management:**

The Brain implements a novel memory architecture that moves beyond traditional vector databases:

- **Topic Heat Calculation**: Dynamically assigns relevance multipliers to conversation topics
- **Memory Scoring Algorithm**: Combines recency, frequency, and contextual relevance for retrieval
- **Cross-Platform Context Synthesis**: Merges conversation history from all platforms into coherent context
- **Autonomous Tool Execution**: Makes independent decisions about memory creation, contact management, and action dispatch

**Technical Architecture:**

- Memory via **SQLite** with custom relevance scoring
- Buffer & conversation state via Ledger synchronization
- Incoming job pings from Scheduler via `POST` endpoints
- Contact resolution via Contacts service
- Outbound action dispatch (email, memory, messaging)
- LLM Tool Execution with autonomous decision-making
- Alerts via Notifications
- Reminders via Stickynotes

**Responsibilities:**

- Cross-platform conversation state management
- Heatmap-based memory retrieval and scoring
- Autonomous tool calling and action dispatch
- Self-prompt modification and behavioral evolution
- Professional relationship management (independent email correspondence)

---

### 📇 Contacts

**Responsibilities:**

- Central identity resolution service
- Stores contact info across platforms (e.g., iMessage ID, Discord, email)
- Supports aliases, metadata, notes
- Enables unified user reference across the stack

---

### 📇 Discord

**Responsibilities:**

- Used as an alerting outgoing mechanism.
- Allows users to sign up and talk to the LLM
- Does not support speaking in servers.

---

### 📺 Divoom

**Responsibilities:**

- Controls Divoom Max display (runs outside Docker due to Bluetooth stack limitations)
- Displays emoji based on conversation tone, topic changes, TTS activity, or system events
- Exposes /send endpoint; accepts emoji input, avoiding redundant updates
- Uses pixoo library for device communication; emoji images stored locally (Twemoji format)
- Selection policy is adaptive, prioritizing meaningful feedback over noise

---

### 💬 iMessage

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

### 🪪 Ledger

**Core Innovation - Cross-Platform Conversation Unification:**

The Ledger is responsible for creating truly unified conversation experiences across all platforms. Unlike traditional chatbots that treat each platform separately, Kirishima maintains a single, continuous conversation thread.

**Technical Architecture:**

- **Message Normalization**: Converts platform-specific message formats into unified internal representation
- **Intelligent Deduplication**: Detects and handles cross-posted messages without losing context
- **Platform-Agnostic Threading**: Maintains conversation flow regardless of communication channel
- **Agent-Centric Perspective**: Logs conversations from the AI's viewpoint, enabling independent relationship building

**Advanced Features:**

- **Email Integration**: Direct email correspondence becomes part of conversation history as `[automated message]` entries
- **Context Preservation**: Switch between voice, text, Discord, iMessage mid-conversation without losing context
- **Message Metadata Tracking**: Timestamps, user ID mapping, tool outputs for accurate recall
- **Buffer Management**: Supplies optimally-sized context windows for multi-turn conversations

**Responsibilities:**

- Maintains persistent, cross-platform conversation buffer using SQLite
- Deduplicates, syncs, and edits message logs from all platforms (e.g., Discord, iMessage, email)
- Supplies the most recent N messages for context in multiturn requests
- Tracks message metadata (timestamps, user ID, tool outputs) for accurate recall
- Authoritative source for conversation history and summary generation
- Enables AI's independent email correspondence and relationship building

---

### 🔁 Proxy

**Core Innovation - Unified LLM Gateway with Autonomous Routing:**

This service handles all LLM interaction with sophisticated prompt scaffolding and autonomous decision-making capabilities. No other service may call the LLM directly.

**Technical Architecture:**

- **Platform-Aware Routing**: Exposes endpoints like `/from/{platform}` and `/to/{platform}` for context-aware processing
- **Dynamic Prompt Scaffolding**: Constructs prompts based on conversation history, memory relevance, and platform context
- **Model Mode Management**: Switches between different behavioral modes (`default`, `work`, `nsfw`) based on context
- **Autonomous Tool Integration**: Enables the AI to independently use tools without explicit user requests

**Advanced Features:**

- **Memory-Informed Prompting**: Integrates heatmap memory scores into prompt construction
- **Cross-Platform Context Injection**: Includes relevant conversation history from all platforms
- **Self-Modification Support**: Handles prompt updates from the AI's own `manage_prompt` tool calls
- **Professional Relationship Context**: Incorporates independent email correspondence and professional identity

**Core Principle:**

- This service acts as the exclusive LLM boundary with full context awareness

**Brain Integration:**

- Store message buffer (incoming & outgoing messages)
- Retrieve conversation summaries for prompt injection with relevance scoring
- Handle `create_memory()` / `delete_memory()` function calls autonomously
- List current memory entries with heatmap scores for prompt construction
- Get/set current mode (`default`, `work`, `nsfw`) based on conversation context
- Schedule tasks via Brain endpoints (which relay to Scheduler)
- Support self-prompt modification and behavioral evolution

**Responsibilities:**

- Centralizes all LLM communication with context-aware prompt scaffolding
- Manages autonomous tool calling and decision-making
- Supports cross-platform conversation continuity
- Enables AI self-modification and professional relationship management
- All LLM requests (including summarization) must pass through this service

---

### ⏱ Scheduler

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

### 🏠 Smarthome

**Responsibilities:**

- Orchestrates natural language control over home automation devices
- Processes user requests to manage lighting, audio, and other smart devices
- Integrates with multiple device types, enabling unified smart home commands
- Acts as the agent’s interface to all home automation endpoints

---

### 🗒️ Stickynotes

**Responsibilities:**

- Manages persistent, context-aware reminders (distinct from push notifications)
- Surfaces reminders only during user interaction—never as unsolicited alerts
- Supports snoozing, recurring, and custom-trigger reminders
- Prompts user for confirmation, snooze, or deletion when surfaced
- Designed for gentle accountability—reminders wait for engagement, not urgency

---

### 📚 Summarize

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

### 🗣️ TTS

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

---

## 🔄 System Data Flow

### Cross-Platform Message Processing

1. **Message Ingestion**: Platform services (Discord, iMessage, Gmail) receive messages
2. **Ledger Normalization**: Messages converted to unified format and deduplicated
3. **Brain Context Assembly**: Retrieves relevant memories using heatmap scoring + recent conversation history
4. **Proxy LLM Processing**: Constructs context-aware prompts and processes through selected LLM
5. **Tool Execution**: AI autonomously decides whether to use tools (memory, contacts, scheduling, etc.)
6. **Response Distribution**: Formatted responses sent back through appropriate platform channels
7. **Memory Update**: New memories created and existing topic heat scores updated based on conversation

### Autonomous Email Correspondence Flow

1. **Direct Email Receipt**: Gmail service receives email sent directly to AI's email address
2. **Conversation Integration**: Email injected into Ledger as `[automated message]` with full context
3. **Professional Context Assembly**: Brain retrieves relevant professional memories and relationship history
4. **Autonomous Response Generation**: AI crafts response based on its own professional identity
5. **Independent Relationship Building**: New memories formed from AI's perspective of the interaction

### Memory Heat Calculation

1. **Topic Extraction**: Keywords and concepts identified from conversation
2. **Usage Frequency Analysis**: How often topics appear in recent conversations
3. **Contextual Relevance Scoring**: How related topics are to current conversation thread
4. **Decay Function Application**: Heat scores naturally decrease when topics aren't referenced
5. **Dynamic Multiplier Assignment**: Topics receive 0.1x-1x multipliers for retrieval ranking

---

## 🧠 Advanced Architecture Components

### Brainlets System

Modular processing pipeline that injects specialized context into conversations:

- **Dynamic Loading**: Brainlets activated based on conversation context and user needs
- **Specialized Processing**: Each brainlet handles specific domains (technical, creative, professional)
- **Context Injection**: Relevant specialized knowledge added to prompt construction
- **Hot-Swappable**: Can be updated or modified without system restart
