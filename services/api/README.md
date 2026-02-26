# API Microservice

OpenAI-compatible REST interface for Kirishima. Translates standard OpenAI API calls into internal requests to the brain service. Runs on `${API_PORT}` (typically 4200).

## Endpoints

### Completions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/completions` | Redirects to `/v1/completions` |
| POST | `/v1/completions` | OpenAI-compatible text completion |
| POST | `/chat/completions` | Redirects to `/v1/chat/completions` |
| POST | `/v1/chat/completions` | OpenAI-compatible chat completion |

### Models

| Method | Path | Description |
|--------|------|-------------|
| GET | `/models` | Redirects to `/v1/models` |
| GET | `/v1/models` | List available modes from config.json |
| GET | `/models/{model_id}` | Redirects to `/v1/models/{model_id}` |
| GET | `/v1/models/{model_id}` | Get details for a specific mode |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ping` | Health check |
| GET | `/__list_routes__` | Lists all registered routes |
| GET | `/docs/export` | Exports internal documentation |

## How It Works

### Mode-Based Model Resolution

This service doesn't expose model names like `gpt-4.1` directly. It uses **modes** defined in `config.json`:

```json
"llm": {
    "mode": {
        "work": {
            "model": "nemo:latest",
            "provider": "ollama",
            "options": { "temperature": 0.3, "max_tokens": 512, "stream": false }
        },
        "default": {
            "model": "gpt-4.1",
            "provider": "openai",
            "options": { "temperature": 0.7, "max_tokens": 1024, "stream": false }
        }
    }
}
```

Clients send the mode name as the `model` parameter. The brain/proxy pipeline resolves the actual provider and model.

### Request Flow

**Single-turn** (`/v1/completions`):
```
Client → API (SingleTurnRequest) → Brain /api/singleturn → Proxy → LLM
```

**Multi-turn** (`/v1/chat/completions`):
```
Client → API (MultiTurnRequest) → Brain /api/multiturn → Proxy → LLM
```

**Special case**: If the first message in a chat completion starts with `### Task`, the request is rerouted to the single-turn pipeline.

### Token Counting

- Single-turn: Uses `tiktoken` (GPT-2 encoding) for prompt token counts
- Multi-turn: Uses token counts returned by the proxy response (`eval_count`, `prompt_eval_count`)

## File Structure

```
app/
├── app.py                    # FastAPI app setup, middleware, router registration
├── completions/
│   ├── singleturn.py         # /v1/completions endpoint logic
│   └── multiturn.py          # /v1/chat/completions endpoint logic
└── models/
    ├── listmodels.py         # /v1/models endpoint
    └── getmodel.py           # /v1/models/{model_id} endpoint
```

## Dependencies

- **Brain service**: All completion requests proxy through brain
- **Config**: `/app/config/config.json` for mode definitions and timeout settings
- **Shared models**: `shared.models.openai`, `shared.models.proxy`, `shared.models.api`

## Known Issues and Recommendations

### Issues

1. **Hardcoded model in task routing** — When a chat completion message starts with `### Task`, the request is rerouted to single-turn with `gpt-4.1-nano` hardcoded (`multiturn.py:123`). Should use the request's model or a config value.

2. **Response model mismatch on redirect endpoints** — Redirect endpoints (e.g., `POST /completions`) declare `response_model=OpenAICompletionResponse` but return `RedirectResponse`. Works due to FastAPI permissiveness, but misleading.

3. **Inconsistent token counting** — Single-turn uses tiktoken locally; multi-turn trusts proxy response counts. Should be standardized.

4. **No config validation on startup** — If `config.json` is missing or malformed, the service crashes with an unhelpful error.

5. **Stale docstring reference to embeddings router** — `app.py` docstring mentions an embeddings router that doesn't exist.

### Recommendations

- Make the task-routing model configurable
- Remove `response_model` from redirect endpoints
- Standardize token counting (prefer proxy counts for both paths)
- Add startup config validation with clear error messages
- Add `__init__.py` files to `completions/` and `models/` subdirectories
