# 🧠 Kirishima

Kirishima is a modular, containerized system designed to orchestrate intelligent reasoning, messaging, and memory across multiple platforms. At the core is **Brain**, an agentic reasoning engine that coordinates interactions between specialized microservices like Summarize, ChromaDB, Scheduler, and Proxy.

> **⚠️ This project is currently undergoing a major rewrite.**  
We are in the process of porting logic from a legacy monorepo into a clean, containerized architecture. All services are being rewritten with stricter routing contracts, simplified responsibilities, and shared message models.

---

## 💡 Project Purpose

Kirishima is designed to:

- Centralize reasoning through a single intelligent agent (**Brain**)
- Support structured, persistent memory using vector search and summarization
- Allow real-time interaction across platforms like iMessage, Email, and OpenWebUI
- Decouple prompt scaffolding, LLM usage, and memory management
- Enable **push-style notification and message delivery** across channels

This architecture is optimized for **agent autonomy**, **contextual reasoning**, and **platform-agnostic communication**.

---

## 🗃️ Documentation

The current documentation set is being carried forward from the previous repo and includes:

- **[Full Architecture.md](docs/Full%20Architecture.md)** – system design and enforcement rules
- **[Ports and Endpoints.md](docs/Ports%20and%20Endpoints.md)** – assigned container ports and service interfaces
- **Per-service specs** (in `docs/Services/`) for:
  - API
  - Brain
  - ChromaDB
  - Contacts
  - iMessage
  - Proxy
  - Scheduler
  - Summarize

These documents reflect both **active design choices** and **legacy constraints** we are migrating away from.

---

## 🐳 Containerization

Kirishima is fully containerized using `docker-compose`. Each microservice runs in its own container and shares common volume mounts for:

- Shared message model classes
- Logging configuration
- Local SQLite data (e.g., for temporary buffers)

---

## 🛠️ Current Rewrite Goals

- Replace OpenAI-style LLM wrappers with direct, structured calls to **Mistral Nemo Instruct 12B Q6_K**
- Separate OpenWebUI-specific quirks from core routing using a new `/messages/api` endpoint in Brain
- Implement dual-layer buffer handling (SQLite + ChromaDB) for resilient context and overwrite support
- Migrate to shared class-based message formats across all services
- Restore full end-to-end messaging for OpenWebUI with retry and function execution logic via Proxy

---

## ✨ Status

- ✅ Docker containers configured
- ✅ Base documentation imported
- 🚧 Rewrite of logic in progress
  - 🚧 API
  - 🚧 Brain
  - 🚧 ChromaDB
  - 🚧 Proxy
  - 🚧 Summarize
- 🚧 LLM integration via Proxy underway
- 🚧 Summarize and Buffer services being refactored

---

## 📫 Contact

This project is in active development. For questions, design proposals, or contributions, please open an issue or discussion thread.
