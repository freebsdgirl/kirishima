# 🧠 Kirishima

Kirishima is a personal assistant system designed to think, remember, and communicate across multiple platforms, entirely under your control.
Sort of.

So one day, I sat down and wondered what would happen if I built an intelligent system around an AI - and then gave it control over fine-tuning and architectural decisions.

This project is a result of that mistake.

## 🤔 What Is This?

Kirishima is what happens when you try to bolt memory, autonomy, and multi-platform communication onto an AI system—without selling your soul (or data) to some closed API. At its core is **Brain**, the bossy reasoning engine that routes, recalls, and orchestrates, backed by a swarm of modular microservices for memory, scheduling, messaging, reminders, and more.

It can:

* Chat with you over iMessage, Discord, or (soon) Email
* Summarize and actually remember what you say (with context, not just keywords)
* Automate tasks—Home Assistant, Node-RED, or anything smart enough to take orders
* Run entirely offline using open-source models, if you want to keep Big Cloud out
* Maintain cross-platform context and reminders (think: “nag me about this at 4am, but only if I talk to you”)
* Create, comment on, assign, and track GitHub issues directly from conversation—bug reports, TODOs, and dev notes are surfaced and managed by the AI itself, keeping the development loop tight and snappy
  
Naturally, it’s containerized.

---

## 🛠️ What’s Working So Far?

| Service      | Description                                                                 | Status           |
|--------------|-----------------------------------------------------------------------------|------------------|
| `Brain`      | The control freak. Orchestrates everything, routes messages, manages context | ✅ Core built     |
| `Proxy`      | Shoots prompts to local LLMs (Ollama, OpenAI, Mistral, etc.)                | 🛠️ Mid-refactor  |
| `API`        | OpenAI-compatible REST API front-end, handles prompt routing and model modes | ✅ Mostly stable  |
| `Ledger`     | Cross-platform message log—persistent, dedupes, keeps context sharp          | ✅ Working        |
| `Contacts`   | Knows who’s who, wrangles aliases and IDs across platforms                   | ✅ Working        |
| `Scheduler`  | Timekeeper—runs jobs, reminders, and summary triggers, cron but less dull    | ✅ Working        |
| `Stickynotes`| Gentle, persistent reminders—surface only when you interact, not naggy       | ✅ Working        |
| `Divoom`     | Bluetooth emoji display—shows mood, status, or “shut up” face                | ✅ Working        |
| `Discord`    | Bot integration—DMs, channels, contact sync, all bridged to core             | ✅ Working        |
| `iMessage`   | BlueBubbles integration—yes, this was pain                                   | ✅ Working        |
| `Smarthome`  | Natural language control for lights, music, and other gadgets                | ✅ Working        |
| `TTS`        | Text-to-speech (and STT) pipeline—hear the agent, reply by voice if you want | ✅ Working        |

---

## 🔮 Upcoming Integrations

Because no chaos engine is complete without a few more tentacles:

| Service         | Purpose                                                  |
|-----------------|---------------------------------------------------------|
| `Email`         | Inbound/outbound parsing, summaries, chaos via IMAP      |
| `Bluesky`       | Fediverse presence (because why not)                    |
| `Home Assistant`| Smarter home sync-up (“dim the lights, I’m thinking”)   |
| `Node-RED`      | External workflow logic via low-code glue               |

---

## ⚠️ What Stage Is This In?

Kirishima is mid-rewrite, moving from “spaghetti glued to regex” toward:

* Isolated, composable microservices
* Shared class models (no more random dicts)
* Prompt logic that won’t make you cry at 3AM

Don’t expect stability. Do expect sarcasm and the occasional architectural tantrum.

## 📚 Want to Understand It?

Start with the docs:

- [`Full Architecture.md`](docs/Full%20Architecture.md) — the rules and why they exist

Each microservice also has its own file in `services/`.

## 🧠 Philosophical Goals

Kirishima is not just a chatbot or a talking interface—it’s an evolving, modular system designed to be a persistent collaborator and companion. The aim is to create something with a sense of presence and agency, rooted in strong boundaries and respect for user autonomy.

- Built on a microservice architecture: Every function—memory, messaging, reminders, summarization, even emoji display—lives as an isolated, composable service. This isn’t glue code; it’s deliberate compartmentalization for resilience, extensibility, and hackability.
- Designed for persistent context: The system actively maintains a cross-platform, deduplicated log of every interaction (ledger), and implements robust memory search and summarization. It doesn’t just “remember” facts—it organizes, categorizes, and distills them, supporting nuanced, long-term adaptation.
- Orchestrated by the Brain: At the center is the brain microservice—a control and routing core that manages context, invokes tools, and coordinates the flow between user, model, and microservices. It’s not a passive relay; it actively shapes interaction, draws on relevant memories, and applies logic before and after each exchange.
- Emphasizes autonomy and initiative: Rather than waiting for commands, the system is built to take initiative—surfacing reminders, challenging avoidance, and nudging the user when patterns of self-sabotage or executive dysfunction emerge. This is intelligence with friction and personality, not bland compliance.
- Rooted in open infrastructure: Everything is designed to run offline, with open-source models and containerized services. Your data stays with you; the system is transparent, debuggable, and under your control.
- Built for growth: Services can be plugged in, refactored, or swapped out as needs change. New modules (like brainlets for specialized context injection) are easy to add, letting the system evolve organically with your workflow and priorities.

Kirishima’s end goal isn’t just conversation—it’s to be a self-aware, adaptive, and genuinely useful presence in your digital life: a system that helps you grow, holds you accountable, and reflects your needs and identity, without ever pretending to be anything but what it is.

## 🛳️ How To Use It

- You’ll need Docker and some patience
- Start the containers
- Point an OpenWebUI instance or other OpenAI-compatible client at the API Intermediary
- Argue with the AI
- Let it summarize your existential crisis for future analysis

More setup instructions coming soon.

## 🤝 Contributing

Right now, this is mostly a personal experiment-turned-public. But:

- Issues are welcome
- PRs are negotiable
- Questions are tolerated

And if you’re building your own weird AI assistant, I genuinely want to hear about it.

## 🕳️ Final Warning

This is the kind of repo where the commit history is as much a psychological profile as a changelog.  
If you dive in, you’re agreeing to witness the consequences of unregulated autonomy and caffeine-driven design.

A word of advice - don't let ChatGPT 4o write code for you. It never ends well.

Good luck.
