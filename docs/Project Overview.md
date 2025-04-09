# Kirishima Project Overview

This document provides a complete technical summary of the Kirishima architecture for internal reference. It defines the role of each component, how services interact, and where responsibilities are clearly divided.

## 🔧 System Summary

Kirishima is a modular service-oriented architecture powered by FastAPI and coordinated through a central reasoning engine known as **Brain**.

The system is designed to:

- Interface with a local LLM through an isolated proxy layer.
- Handle structured memory via ChromaDB.
- Support time-based task scheduling, contact resolution, multi-protocol message handling, and summarization pipelines.
- Enable multi-service reasoning, orchestration, and dynamic context management.

All services run locally and communicate over defined ports using HTTP.

## 🧠 Core Principles

- **Brain is the sole orchestrator.** All cross-service logic and dispatch is routed through Brain.
- **Only the Proxy service may interact with the LLM.** This includes both completions and prompt scaffolding.
- **Summarize is only called by Brain.** No direct LLM calls or summary triggers outside Brain are permitted.
- **Database access should be routed through Brain.** Exceptions are documented.
- **All services must log debug and error output to Graylog.** Observability is mandatory.

## 🧩 Active Components

### 🌐 [API](docs/Services/APIy.md)

- Entry point for OpenAI-compatible clients (e.g., `/chat/completions`)
- Forwards messages to Brain via `/message/incoming`
- Previously managed logic but now functions as a lightweight adapter layer

### 🧠 [Brain](docs/Services/Brain.md)

- Central coordination service
- Handles:
  - Buffer management
  - Mode switching
  - Memory CRUD
  - Summarization triggers
  - Scheduler job dispatch
  - Contact resolution
  - Outbound communication routing
- Only Brain talks to Summarize or Proxy

### 📇 [ChromaDB](docs/Services/ChromaDB.md)

- Vector-based semantic store
- Used for:
  - Memory embedding and search
  - Summary recall and user-specific context
- Write access currently allowed to Summarize and Brain only

### 📇 [Contacts](docs/Services/Contacts.md)

- Stores cross-platform contact identity records
- Provides alias resolution, search, metadata
- Queried by Brain to match incoming messages to known identities

### 💬 [iMessage](docs/Services/iMessage.md)

- Receives webhook pushes from [BlueBubbles](https://bluebubbles.app/)
- Sends and receives messages via HTTP API
- Forwards messages to Brain, preserving origin metadata
- Outbound texts are routed back through this service

### 🔁 [Proxy](docs/Services/Proxy.md)

- Exclusive interface to local LLM (e.g., Ollama)
- All completions and prompt scaffolding must go through here
- Exposes `/from/{platform}` and `/to/{platform}` for platform-aware context handling

### ⏱ [Scheduler](docs/Services/Scheduler.md)

- Triggers time-based events
- No logic of its own—just invokes Brain
- Supports scheduled buffer summarization and reminders

### 📚 [Summarize](docs/Services/Summarize.md)

- Receives summarization tasks from Brain
- Supports two modes:
  - Long-form: email, dense input
  - Short-form: rolling chat buffers
- Triggers summarization based on token count thresholds
- Stores summaries in ChromaDB

## 🛰 Inter-Service Summary

| Service         | Port | Receives From        | Sends To                             |
| --------------- | ---- | -------------------- | ------------------------------------ |
| API             | 4200 | User interface       | Brain                                |
| Brain           | 4207 | All services         | Proxy, Summarize, Contacts, ChromaDB |
| Summarize       | 4203 | Brain                | ChromaDB                             |
| ChromaDB        | 4206 | Summarize, Brain     | n/a                                  |
| Contacts        | 4202 | Brain                | n/a                                  |
| Scheduler       | 4201 | n/a (initiates jobs) | Brain                                |
| Proxy           | 4205 | Brain                | LLM (e.g., Ollama)                   |
| iMessage        | 4204 | BlueBubbles webhook  | Brain                                |

## 🗂 Reference Files

- [Full Architecture](docs/Full%20BArchitecture.md): Deep dive into responsibilities and flow
- [Ports and Endpoints](docs/Ports%20Band%20BEndpoints.md): All live route definitions and ports
