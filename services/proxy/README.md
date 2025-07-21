# Proxy Micr## Endpoints

- `POST /completions`  
  Direct, "dumb" LLM calls. Specify the model; provider defaults to Ollama for `nemo:latest` unless overridden. Prompts are sent in instruct format for Ollama with `raw=true`.
- `POST /chat/completions`  
  Mode-driven, context-rich LLM calls. "Mode" is mapped to a concrete model, provider, and options. Loads app.prompts.{provider}-{mode} and builds the system prompt using context (memories, summaries, time, etc). Final prompt is rendered using a mode-specific Jinja template.
- `POST /api/multiturn`  
  Multi-turn conversation processing with context management and tool execution.
- `POST /api/singleturn`  
  Single-turn LLM requests for simple operations without conversation history.
- `POST /summary/user`  
  Generate user-specific summaries from conversation data.
- `POST /summary/user/combined`  
  Generate combined summaries across multiple time periods.
- `POST /json`  
  JSON-specific processing and formatting endpoint.
- `POST /queue/enqueue`  
  Manually enqueue tasks in the provider-specific processing queues.
- `GET /queue/status`  
  Get current status of all provider queues.
- `GET /queue/task/{task_id}`  
  Get status and results of a specific queued task.ce

Acts as the LLM gateway for the system. Handles all communication with Ollama and OpenAI models, encapsulating prompt construction, provider/model resolution, and queue-based request dispatch.

## Features

- Supports both /completions (direct model access) and /chat/completions (mode-based, context-aware)
- Dynamically resolves provider/model/options using config.json
- Flexible system prompt construction via provider/mode-specific prompt modules and Jinja templates
- Multiturn prompt formatting (Ollama gets instruct-style [INST] blocks, OpenAI uses native format)
- All requests are queued (per-provider, with priority support) and processed asynchronously

## Endpoints

- `POST /completions`  
  Direct, “dumb” LLM calls. Specify the model; provider defaults to Ollama for `nemo:latest` unless overridden. Prompts are sent in instruct format for Ollama with `raw=true`.
- `POST /chat/completions`  
  Mode-driven, context-rich LLM calls. “Mode” is mapped to a concrete model, provider, and options. Loads app.prompts.{provider}-{mode} and builds the system prompt using context (memories, summaries, time, etc). Final prompt is rendered using a mode-specific Jinja template.

## How It Works

- /chat/completions:
    - Accepts a “mode”, resolves provider/model/options from config
    - Loads the prompt module for that provider/mode, constructs context, and renders the system prompt
    - Multiturn prompt is formatted for the provider (Ollama: instruct-style, OpenAI: as-is)
    - Enqueues the job in the relevant provider queue with optional priority

- /completions:
    - Accepts explicit model (and optionally provider)
    - Formats prompt for instruct models (Ollama) and sends with `raw=true`
    - Enqueues the job in the matching queue

- Both endpoints use per-provider queues (Ollama, OpenAI), supporting priority and async processing

## Configuration

- All provider/model/option mappings live in `config.json`
- Prompt modules live in `app/prompts/`, one per provider-mode combination
- Jinja templates determine actual prompt formatting per mode

## Notes & Gotchas

- Prompt module/template indirection adds complexity, but enables deep customization
- Everything is async and queue-driven; no synchronous LLM calls
- Watch for queue contention under heavy load
- Extendable for future LLM providers/models—just add a prompt module and config entry