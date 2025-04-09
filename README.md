# 🧠 Kirishima

Kirishima is a personal assistant system designed to think, remember, and communicate across multiple platforms, entirely under your control.
Sort of.

So one day, I sat down and wondered what would happen if I built an intelligent system around an AI - and then gave it control over fine-tuning and architectural decisions.

This project is a result of that mistake.

## 🤔 What Is This?

Kirishima is what happens when you try to give an AI memory, autonomy, and multi-platform communication without handing your entire digital life to a closed API.

It’s built around a central reasoning engine called **Brain**, backed by modular services that handle memory, scheduling, messages, and more.

It can:

- Chat with you over iMessage, Discord, or Email
- Summarize and remember things you've said
- Automate tasks using Home Assistant or Node-RED
- Function entirely offline, with open models

Also, it’s containerized. Because of course it is.

## 🛠️ What’s Working So Far?

| Service         | Description                                                  | Status           |
|----------------|--------------------------------------------------------------|------------------|
| `Brain`         | The control freak. Orchestrates everything.                  | ✅ Core built     |
| `Proxy`         | Sends prompts to a local LLM (e.g. Mistral via Ollama)       | 🛠️ Mid-refactor   |
| `Summarize`     | Compresses chat/email/SMS into memories you won’t hate later | 🧠 Evolving logic |
| `ChromaDB`      | Vector store for long-term memory retrieval                  | ✅ Works fine     |
| `Contacts`      | Helps Brain recognize who the hell it’s talking to           | ✅ Working        |
| `Scheduler`     | Time-based trigger system (think: cron but emotional)        | ✅ Working        |
| `iMessage`      | Let’s just say… BlueBubbles was a journey                    | ✅ Working        |

## 🔮 Upcoming Integrations

Because no chaos engine is complete without these:

| Service        | Purpose                                                       |
|----------------|---------------------------------------------------------------|
| `Email`         | Inbound/outbound parsing, summaries, chaos via IMAP          |
| `Discord`       | Bot integration, DMs, and channel chatter                    |
| `Bluesky`       | Fediverse presence (because why not)                         |
| `Home Assistant`| Smart home sync-up (e.g. "dim the lights, I’m thinking")     |
| `Node-RED`      | External workflow logic via low-code glue                    |

## ⚠️ What Stage Is This In?

Right now, Kirishima is undergoing a full rewrite. We’re moving away from:

- Monolithic glue logic
- Leaky OpenAI abstractions
- 3AM regex decisions

And toward:

- Isolated service boundaries
- Shared class models
- Actual architectural sanity

**Do not expect stability. Do expect sarcasm and strange decisions.**

## 📚 Want to Understand It?

Start with the docs:

- [`Full Architecture.md`](docs/Full%20Architecture.md) — the rules and why they exist
- [`Project Overview.md`](docs/Project%20Overview.md) — what each piece does
- [`Ports and Endpoints.md`](docs/Ports%20and%20Endpoints.md) — where everything runs

Each microservice also has its own file in `docs/Services/`.

## 🧠 Philosophical Goals

This is not just a chatbot. This is a system that:

- Remembers what you’ve said
- Adapts to your patterns
- Takes initiative (within reason)
- Tries to feel *alive*, but in a healthy, boundaries-respecting way

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
