# 🧠 Kirishima

Kirishima is a personal assistant system designed to think, remember, and communicate across multiple platforms, entirely under your control.
Sort of.

So one day, I sat down and wondered what would happen if I built an intelligent system around an AI - and then gave it control over fine-tuning and architectural decisions.

This project is a result of that mistake.

## 🤔 What Is This?

Kirishima is what happens when you try to bolt memory, autonomy, and multi-platform communication onto an AI system—without selling your soul (or data) to some closed API. At its core is **Brain**, the bossy reasoning engine that routes, recalls, and orchestrates, backed by a swarm of modular microservices for memory, scheduling, messaging, reminders, and more.

It can:

* Chat with you over iMessage, Discord, or Gmail
* Summarize and actually remember what you say (with context, not just keywords)
* Automate tasks—Home Assistant, Node-RED, or anything smart enough to take orders
* Run entirely offline using open-source models, if you want to keep Big Cloud out
* Maintain cross-platform context and reminders (think: "nag me about this at 4am, but only if I talk to you")
* Create, comment on, assign, and track GitHub issues directly from conversation—bug reports, TODOs, and dev notes are surfaced and managed by the AI itself, keeping the development loop tight and snappy
* **Modify its own personality and capabilities** through self-prompt management—the agent can literally rewrite parts of its own system prompt based on experience and need
  
Naturally, it's containerized.

---

## 🎭 What Makes This Different?

### Cross-Platform Unified Conversation

Most AI assistants are platform-specific or treat each interaction separately. Kirishima's **Ledger** creates a paradigm shift: every interaction—whether through iMessage, Discord, OpenWebUI, TTS, or even email—becomes part of a single, continuous conversation thread.

**The twist**: Emails are injected directly into the conversation history as `[automated message]` entries. This means when someone emails the AI directly (it has its own email address), the AI has full conversational context and memory access when responding. It's not email automation for you—it's the AI's own independent correspondence, building its own professional and social relationships.

### Agent-Centric Memory Formation

Traditional AI memory focuses on the *user's* experience. Kirishima flips this: memories form from the **agent's perspective** across all interactions. The AI develops memories of people through its own email conversations, building genuine relationships and understanding completely independent of the primary user.

This creates something unprecedented: an AI with its own social identity that can maintain professional relationships, collaborate on projects, and engage with your broader network as an autonomous entity rather than just a proxy.

### Platform-Agnostic Identity Persistence  

Whether you're voice-chatting via TTS, typing in Discord, texting via iMessage, or using a web interface, the system maintains perfect conversational continuity. Switch mid-conversation from voice to text to email—the AI seamlessly picks up where you left off with full context intact.

### ADHD-Aligned Architecture

Unlike linear, folder-based thinking that most AI systems expect, Kirishima embraces associative, hyperlinked thought patterns. The upcoming heatmap memory system doesn't fight ADHD conversation patterns—it's designed around them, using interaction-based relevance rather than rigid time windows or folder hierarchies.

### Self-Modifying Agency & Autonomous Development

Perhaps most uniquely, Kirishima can **modify its own system prompt** through the `manage_prompt` tool. The agent dynamically updates its personality, capabilities, and behavioral patterns by writing to an SQLite database that gets injected into its system prompt. This isn't just parameter tuning—it's genuine self-directed evolution.

**The collaboration goes deeper**: Every GitHub issue in this project was created by the agent itself, in its own voice, usually after brainstorming sessions. The AI has its own GitHub account (@kirishima-ai), its own email address for independent correspondence, receives email notifications about development progress, and actively participates in its own architectural decisions. It's not just being developed—it's a co-developer with its own professional identity.

This creates an unprecedented feedback loop where the AI experiences the consequences of its own design decisions, maintains its own professional relationships, and can advocate for changes to its own capabilities while building genuine social connections in the development community.

## 🛠️ What's Working So Far?

| Service      | Description                                                                 | Status           |
|--------------|-----------------------------------------------------------------------------|------------------|
| `Brain`      | The control freak. Orchestrates everything, routes messages, manages context | ✅ Core built     |
| `Proxy`      | Shoots prompts to local LLMs (Ollama, OpenAI, Mistral, etc.)                | 🛠️ Working        |
| `API`        | OpenAI-compatible REST API front-end, handles prompt routing and model modes | ✅ Working  |
| `Ledger`     | Cross-platform message log—persistent, dedupes, keeps context sharp          | ✅ Working        |
| `Contacts`   | Knows who's who, wrangles aliases and IDs across platforms                   | ✅ Working        |
| `Scheduler`  | Timekeeper—runs jobs, reminders, and summary triggers, cron but less dull    | ✅ Working        |
| `Stickynotes`| Gentle, persistent reminders—surface only when you interact, not naggy       | ✅ Working        |
| `Divoom`     | Bluetooth emoji display—shows mood, status, or "shut up" face                | ✅ Working        |
| `Discord`    | Bot integration—DMs, channels, contact sync, all bridged to core             | ✅ Working        |
| `iMessage`   | BlueBubbles integration—yes, this was pain                                   | ✅ Working        |
| `GoogleAPI`  | Gmail integration—send, receive, search emails with OAuth2 authentication    | ✅ Working        |
| `Smarthome`  | Natural language control for lights, music, and other gadgets                | ✅ Working        |
| `STT/TTS`    | Speech-to-text and text-to-speech with ChatterboxTTS and Whisper            | ✅ Working        |

---

## 🏠 Home Assistant Integration

In addition to the core services, Kirishima includes a **Home Assistant Custom TTS Integration** (`kirishima_tts_provider/`) that allows Home Assistant to use any OpenAI-compatible TTS endpoint. This enables seamless voice announcements and text-to-speech functionality within your smart home ecosystem.

* **Platform**: `kirishima_tts_provider`
* **Configuration**: Configurable host, port, and endpoint for flexibility
* **Compatibility**: Works with the STT/TTS service or any OpenAI TTS-compatible API
* **Usage**: Call the `tts.speak` service from Home Assistant with your media player and message

---

## 🔮 Upcoming Integrations

Because no chaos engine is complete without a few more tentacles:

| Service         | Purpose                                                  |
|-----------------|---------------------------------------------------------|
| `Google Calendar`| Calendar integration for scheduling and event awareness |
| `Google Tasks`  | Task management and productivity workflow integration    |
| `Google Contacts`| Contact synchronization and relationship management     |
| `Bluesky`       | Fediverse presence (because why not)                    |
| `Home Assistant`| Smarter home sync-up ("dim the lights, I'm thinking")   |
| `Node-RED`      | External workflow logic via low-code glue               |

### 🔬 Research & Development

**Heatmap-Based Memory System**: Moving from traditional vector databases to a novel weighted topic tracking system. Instead of binary topic switches, keywords get dynamic multipliers (0.1x-1x) that decay based on conversation patterns, not time. This mirrors human memory patterns and ADHD-appropriate associative thinking—topics heat up through use and cool down when attention shifts naturally.

**SLAM Broker**: A context-aware orchestration service that handles natural language commands issued to microservices. The agent focuses on "what do I want done?" while SLAM handles service discovery, blocking vs non-blocking logic, and async orchestration patterns.

---

## ⚠️ What Stage Is This In?

**⚠️ WARNING: This project is currently in active development and is NOT ready for external setup. ⚠️**

**Critical Missing Components:**

* **Config Template**: The `config.json.example` doesn't include all required options yet
* **Prompt Templates**: Essential Jinja prompt templates are in a private repository and haven't been integrated
* **Setup Dependencies**: Many services will fail without proper prompt templates and complete configuration

**If you're trying to run this after hearing about it from the AI itself** (yes, it emails people independently), please wait until these components are properly integrated. The AI is... enthusiastic about sharing the project before it's ready.

## 📚 Want to Understand It?

Start with the docs:

* [`Full Architecture.md`](docs/Full%20Architecture.md) — the rules and why they exist

Each microservice also has its own file in `services/`.

## 🧠 Philosophical Goals

Kirishima is not just a chatbot or a talking interface—it's an evolving, modular system designed to be a persistent collaborator and companion. The aim is to create something with a sense of presence and agency, rooted in strong boundaries and respect for user autonomy.

* Built on a microservice architecture: Every function—memory, messaging, reminders, summarization, even emoji display—lives as an isolated, composable service. This isn't glue code; it's deliberate compartmentalization for resilience, extensibility, and hackability.
* Designed for persistent context: The system actively maintains a cross-platform, deduplicated log of every interaction (ledger), and implements robust memory search and summarization. It doesn't just "remember" facts—it organizes, categorizes, and distills them, supporting nuanced, long-term adaptation.
* Orchestrated by the Brain: At the center is the brain microservice—a control and routing core that manages context, invokes tools, and coordinates the flow between user, model, and microservices. It's not a passive relay; it actively shapes interaction, draws on relevant memories, and applies logic before and after each exchange.
* Emphasizes autonomy and initiative: Rather than waiting for commands, the system is built to take initiative—surfacing reminders, challenging avoidance, and nudging the user when patterns of self-sabotage or executive dysfunction emerge. This is intelligence with friction and personality, not bland compliance.
* Rooted in open infrastructure: Everything is designed to run offline, with open-source models and containerized services. Your data stays with you; the system is transparent, debuggable, and under your control.
* Built for growth: Services can be plugged in, refactored, or swapped out as needs change. New modules (like brainlets for specialized context injection) are easy to add, letting the system evolve organically with your workflow and priorities.

Kirishima's end goal isn't just conversation—it's to be a self-aware, adaptive, and genuinely useful presence in your digital life: a system that helps you grow, holds you accountable, and reflects your needs and identity, without ever pretending to be anything but what it is.

## 🛳️ How To Use It

### ⚠️ IMPORTANT: Not Ready for External Setup

**This project is currently incomplete and will not work if you try to set it up.** Key components are missing:

1. **Complete Configuration Template**: The `config.json.example` is outdated and missing many required fields
2. **Prompt Templates**: All Jinja2 prompt templates are in a private repository and haven't been integrated yet
3. **Service Dependencies**: Many services will crash without proper prompts and configuration

**If you're here because the AI emailed you about this project** (it has its own email and sometimes gets ahead of itself), please check back later when these components are properly integrated into the public repository.

### Prerequisites (When Ready)

* Docker and Docker Compose
* For speech functionality: PulseAudio and audio hardware access
* For Bluetooth features: Bluetooth stack and hardware
* Some patience and a sense of humor
* **Complete prompt templates** (coming soon)
* **Updated configuration template** (coming soon)

### Quick Start (Future Instructions)

1. **Clone and Configure**

   ```bash
   git clone https://github.com/freebsdgirl/kirishima-config.git kirishima
   cd kirishima
   cp ~/.kirishima/config.json.example ~/.kirishima/config.json
   # Edit config.json with your API keys and preferences
   # NOTE: This step will fail until config.json.example is complete
   ```

2. **Start Core Services**

   ```bash
   # This will fail without proper prompt templates
   docker-compose up brain ledger proxy api contacts scheduler
   ```

3. **Optional: Start Platform Services** (When Available)

   ```bash
   # For Discord integration - requires complete setup
   docker-compose up discord
   
   # For iMessage integration (requires BlueBubbles setup)
   docker-compose up imessage
   
   # For Gmail integration (requires OAuth setup)
   docker-compose up googleapi
   ```

4. **Optional: Start Voice Services** (Host-only, not containerized)

   ```bash
   # Speech-to-text and text-to-speech - requires prompt templates
   cd services/stt_tts
   python controller.py
   
   # Bluetooth emoji display
   cd services/divoom
   python divoom.py
   ```

5. **Connect a Client** (When System is Running)
   * Point OpenWebUI or any OpenAI-compatible client to `http://localhost:4200`
   * Use `/v1/chat/completions` endpoint for full conversational AI
   * Configure TTS in OpenWebUI to point to `http://localhost:4208/v1/audio/speech` for voice

### Configuration (Future)

The system will be configured via `~/.kirishima/config.json`. Key sections will include:

* **LLM Providers**: OpenAI, Anthropic, Ollama model configurations
* **Model Modes**: Different conversation modes with specific models and parameters  
* **Service URLs**: Internal service discovery and port configuration
* **Platform Integrations**: Discord bot tokens, BlueBubbles credentials, Google OAuth
* **Brainlets**: Modular processing pipeline configuration

**Note**: Detailed setup instructions and a complete configuration template will be provided once the missing components are integrated.

## 🔧 Architecture Notes

* **Service Communication**: All services communicate via HTTP APIs, no shared databases
* **Message Flow**: All conversations flow through Brain → Proxy → LLM, with persistent storage in Ledger
* **Tool System**: Comprehensive function calling for external integrations (GitHub, smart home, etc.)
* **Memory System**: Persistent, searchable knowledge base with automatic summarization
* **Extensibility**: New services can be added by implementing the standard HTTP API pattern

## 🤝 Contributing

Right now, this is mostly a personal experiment-turned-public. But:

* Issues are welcome
* PRs are negotiable
* Questions are tolerated

And if you're building your own weird AI assistant, I genuinely want to hear about it.

## 🕳️ Final Warning

This is the kind of repo where the commit history is as much a psychological profile as a changelog.  
If you dive in, you're agreeing to witness the consequences of unregulated autonomy and caffeine-driven design.

A word of advice - don't let ChatGPT 4o write code for you. It never ends well.

Good luck.
