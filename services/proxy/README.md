# Proxy Microservice

Sole LLM gateway for the system. Handles prompt construction, provider/model resolution, and direct dispatch to LLM providers. No other service talks to LLMs directly. Runs on `${PROXY_PORT}`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/singleturn` | Simple mode-based completion (no context, no tools) |
| POST | `/api/multiturn` | Full multi-turn with system prompt, tools, memories, summaries |
| POST | `/api/responses` | Responses-style mode-based request using shared prompt construction |
| ANY | `/queue/*` | Returns HTTP 410 — queue system has been removed |

System endpoints: `/ping`, `/__list_routes__`, `/docs/export`

## How It Works

### Mode → Provider Resolution

All three endpoints accept a `model` field that's actually a **mode name** (e.g., `default`, `work`, `claude`). The proxy resolves it to a concrete provider/model/options via `config.json`:

```json
"llm": {
    "mode": {
        "default": { "model": "gpt-4.1", "provider": "openai", "options": {...} },
        "work":    { "model": "gpt-4o", "provider": "openai", "options": {...} },
        "claude":  { "model": "claude-sonnet-4-20250514", "provider": "anthropic", "options": {...} },
        "nsfw":    { "model": "nemo:latest", "provider": "ollama", "options": {...} },
        "router":  { "model": "gpt-4.1-nano", "provider": "openai", "options": {...} }
    }
}
```

If the requested mode isn't found, falls back to `default`.

### Providers

| Provider | Dispatch | Format |
|----------|----------|--------|
| `openai` | `POST /v1/chat/completions` and `POST /v1/responses` (OpenAI API) | Native chat / responses |
| `anthropic` | `POST /v1/chat/completions` (Anthropic OpenAI-compat endpoint) | Chat-completions compatibility |
| `ollama` | `POST /api/generate` (local Ollama) | Instruct-style `[INST]<<SYS>>...<</SYS>>[/INST]`, `raw=true` |

All dispatch is **synchronous** (direct HTTP call, no queue). The old async queue system was fully removed.

### Prompt Construction

The prompt system uses a two-tier approach:

1. **Centralized prompts** (preferred): JSON context files at `/app/config/prompts/proxy/contexts/{provider}-{mode}.json` with fallback to shared files like `default-{mode}.json` + Jinja2 templates at `/app/config/prompts/proxy/templates/{template}.j2`
2. **Legacy module prompts** (fallback): Python modules at `app/prompts/{provider}-{mode}.py` with `build_prompt()` functions

The dispatcher (`prompts/dispatcher.py`) tries centralized first, falls back to legacy modules.

Context available to templates: `memories`, `summaries`, `time`, `agent_prompt`, `username`, `platform`.

### SingleTurn Flow

```
SingleTurnRequest(model, prompt)
  → resolve mode → (provider, model, options)
  → wrap prompt for provider format
  → dispatch to provider
  → ProxyResponse(response, eval_count, prompt_eval_count, timestamp)
```

### MultiTurn Flow

```
MultiTurnRequest(model, messages, memories, summaries, tools, username, platform, agent_prompt)
  → resolve mode → (provider, model, options)
  → build system prompt via dispatcher (centralized or legacy)
  → format messages for provider (instruct-style for Ollama, native for OpenAI/Anthropic)
  → include tools with tool_choice="auto" (OpenAI/Anthropic only; Ollama ignores tools)
  → dispatch to provider
  → normalize response (extract tool_calls, function_call, token counts)
  → ProxyResponse
```

### Responses Flow

```
ResponsesRequest(model, input, tools?, agent_prompt?)
  → resolve mode → (provider, model, options)
  → build shared system prompt via dispatcher
  → openai: POST /v1/responses
  → anthropic: translate to chat messages and use existing compat path
  → ProxyResponse
```

### Tool Support

- Tools are passed through from the request to OpenAI/Anthropic providers
- `tool_choice` is hardcoded to `"auto"` (not configurable from caller)
- Ollama doesn't support tool calls — tools silently ignored
- Response normalizes `tool_calls` as lists (OpenAI may return single objects)

## File Structure

```
app/
├── app.py                          # FastAPI setup, middleware, tracing
├── routes/
│   ├── openai.py                   # /api/singleturn, /api/multiturn, /api/responses route definitions
│   └── queue.py                    # Returns 410 for removed queue endpoints
├── services/
│   ├── completions.py              # SingleTurn handler
│   ├── chat_completions.py         # MultiTurn handler (system prompt, context)
│   ├── responses.py                # Responses handler (shared prompt + provider dispatch)
│   ├── util.py                     # _resolve_model_provider_options(), _create_memory_str()
│   ├── send_to_ollama.py           # Ollama dispatch (POST /api/generate)
│   ├── send_to_openai.py           # OpenAI dispatch (POST /v1/chat/completions)
│   ├── send_to_openai_responses.py # OpenAI dispatch (POST /v1/responses)
│   ├── send_to_anthropic.py        # Anthropic dispatch (OpenAI-compat endpoint)
│   ├── is_instruct_model.py        # Queries Ollama /api/show for instruct detection
│   ├── send_prompt_to_llm.py       # DEAD CODE — unused legacy function
│   └── queue.py                    # Stub — logs queue removal
└── prompts/
    ├── dispatcher.py               # Centralized → legacy fallback routing
    ├── centralized_loader.py       # JSON context + Jinja2 template loading
    ├── util.py                     # Jinja2 environment setup (legacy templates)
    ├── guest.py                    # BROKEN — import path wrong after refactor
    └── work.py                     # BROKEN — same import issue as guest.py
```

## Dependencies

- **Brain service**: Calls `/api/singleturn` and `/api/multiturn`
- **Config**: `/app/config/config.json` for mode/provider/model mappings
- **Prompt templates**: `/app/config/prompts/proxy/` (centralized system)
- **External APIs**: OpenAI, Anthropic, local Ollama

## Known Issues and Recommendations

### Issues

1. **Broken legacy prompt modules** — `guest.py` and `work.py` import `from app.util import create_memory_str`, but `app/util.py` was removed. Function lives at `app.services.util._create_memory_str`. If centralized prompts fail, fallback crashes with ImportError.

2. **Dead code: `send_prompt_to_llm.py`** — References old config structure (`_ollama['server_url']`). Never called anywhere. Should be deleted.

3. **Queue system references in old docs** — Architecture docs and copilot instructions still reference async queues, workers, and priority dispatch. All of that is gone — dispatch is now synchronous.

4. **Config loaded fresh on every request** — `_resolve_model_provider_options()` opens and parses `config.json` on every call. Should cache with optional hot-reload.

5. **No streaming support** — All requests set `stream=False`. Config has stream options but they're never used.

6. **Mode vs. model naming confusion** — `MultiTurnRequest.model` and `SingleTurnRequest.model` are actually mode names, not model names. Misleading field naming.

7. **Anthropic uses OpenAI-compat endpoint** — Works but doesn't leverage Anthropic's native Messages API, which has richer tool support and better error handling.

8. **No retry logic** — Transient provider failures (rate limits, timeouts) cause immediate 500s. No retry, backoff, or fallback.

### Recommendations

- Delete `send_prompt_to_llm.py` and fix or remove `guest.py`/`work.py`
- Add config caching (reload on file change or periodic interval)
- Add basic retry logic for transient provider failures
- Consider streaming support for long responses
- Update architecture docs to reflect sync direct dispatch
