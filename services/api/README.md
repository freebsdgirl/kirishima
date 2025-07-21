
# API Microservice

The API microservice is the user-facing OpenAI-compatible interface for the Kirishima system. It typically runs on port 4200 and handles the following endpoints:

## Endpoints

- `POST /completions` and `POST /v1/completions` — OpenAI-compatible completion endpoint
- `POST /chat/completions` and `POST /v1/chat/completions` — OpenAI-compatible chat completion endpoint  
- `GET /models` and `GET /v1/models` — List available models/modes
- `GET /models/{model_id}` and `GET /v1/models/{model_id}` — Get details for a specific model/mode

## Models and Modes

Unlike the OpenAI API, this service does not expose model names like `gpt-4.1` directly. Instead, it uses "modes" defined in the global `config.json`. Each mode specifies:

- The actual model name
- The provider (e.g., OpenAI, Ollama)
- Per-mode generation options (e.g., temperature, max_tokens, streaming)

This allows users to switch between different models and configurations by updating the `config.json`, not the codebase.

### Example `config.json` Entry

```json
"llm": {
    "mode": {
        "work": {
            "model": "nemo:latest",
            "provider": "ollama",
            "options": {
                "temperature": 0.3,
                "max_tokens": 512,
                "stream": false
            }
        },
        "default": {
            "model": "gpt-4.1",
            "provider": "openai",
            "options": {
                "temperature": 0.7,
                "max_tokens": 1024,
                "stream": false
            }
        }
    }
}
```

To change the active model or its parameters, simply edit the appropriate mode in `config.json`.

## Summary

- OpenAI-compatible endpoints, local or remote providers
- Model and config switching via `config.json` modes
- No OpenAI model name exposure—modes only

For details on endpoint usage, see the OpenAI API documentation (most request/response patterns are supported).
