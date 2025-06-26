# Brain Microservice

The brain service is the core orchestrator, traffic cop, and context engine behind the Kirishima system. If API is the polite receptionist, brain is the one actually making things happen (and cleaning up everyone else’s mess).

## Core Responsibilities

- Orchestrates /chat/completions and (to a lesser extent) /completions requests
- Runs “brainlets” for modular pre- and post-processing
- Handles context, memory, tool invocation, and cross-service coordination
- Manages notifications, scheduler jobs, and tool definitions
- Integrates with Discord, iMessage, and other platform-specific micros
- Legacy and transitional code lives here—expect sharp edges

## Major Endpoints

### /chat/completions

The workhorse. Handles a full round-trip flow:

- Retrieves memories and user context
- Runs pre-execution brainlets (modular small tasks, e.g. keyword extraction)
- Sends request to proxy service
- Handles tool calls and function execution (e.g., GitHub, smart home)
- Syncs messages with ledger service
- Runs post-execution brainlets (e.g., injects memories, triggers divoom emoji updates)

### /completions

Single-turn only—just proxies to proxy. No orchestration, no memory, no tools. Only brain should talk to proxy directly.

### Discord Endpoint

Receives requests from the Discord microservice, adds platform-specific junk (user IDs, etc.), then forwards to proxy. Still uses a legacy custom endpoint on proxy—needs to be updated to use proxy’s multiturn endpoint.

### Memory Endpoints

Legacy only—point at chromadb’s old vector memory. Should be retired once Discord and iMessage are updated to new memory infra.

### Notifications Endpoints

CRUD for notifications (stored in SQLite, slated for migration to the courier service). Handles delivery to iMessage and Discord, falling back as needed. Deletes notifications after delivery.

### Scheduler Endpoints

Proxies for the scheduler service—brain gets pinged for jobs like checking notifications and generating summaries. Jobs themselves just trigger summary/notification logic here.

### Summary Endpoints

Summary logic lives here, called by scheduler jobs—not typically hit directly.

### Tools Endpoints

Manages in-system tools: GitHub ticketing, prompt management, memory ops, smart home, TTS, Divoom, etc. Tool definitions live in tools.json. Memory tools are fragmented and need consolidation.

### Embedding Endpoint

Exists. No one remembers why. Don’t touch unless you like existential dread.

### iMessage Endpoint

Like Discord, but for the iMessage microservice.

### Old Mode Setting

Ignore. Needs deleting.

## Brainlets

Modular little jobs that run before or after the main completions call, typically for lightweight, model-driven tasks (keyword tagging, emoji selection, topic tracking). Output gets piped into pseudo tool output for LLM context injection.

- divoom: updates the emoji display
- memory_search: retrieves and injects memories
- topic_tracker: retired, but code is still around

## Tools

Brain manages and invokes all system tools, including:

- GitHub issue/comment management (in its own voice)
- Prompt management
- Memory CRUD (soon to be unified)
- Smarthome controls
- TTS toggling
- Divoom emoji pushes

## Sharp Edges, TODOs & Legacy

- Memory endpoints are legacy—pending removal
- Notifications are moving out to courier
- Discord endpoint needs to switch to proxy multiturn
- Old mode-setting code is obsolete
- Embedding endpoint: likely dead code
- Tools are fragmented—needs refactor

## Summary

Brain is where the magic (and the mess) happens. If something feels convoluted, it probably is—but that’s where all the system’s context, memory, and tool integration are wired together.

---

If you’re working on brain: expect to find skeletons. Ask questions, read comments, and don’t trust anything that hasn’t been used in production this week.
