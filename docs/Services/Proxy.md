
# 🔁 Proxy

## Purpose
The Proxy service acts as the exclusive interface to the language model (LLM). All prompt generation and completions are centralized here to enforce consistent formatting, platform-specific adaptation, and usage isolation. This service ensures that no other part of the Kirishima system talks to ollama directly.

## Port
4205

---

## Endpoints

### `POST /from/imessage`

Handles LLM requests for messages originating from the [[iMessage]] platform.

**Input Model:** `ProxyRequest`
- `message`: incoming user message
- `user_id`: identity string
- `context`: retrieved summarization context
- `mode`: optional system mode (used for prompt selection)
- `memories`: optional list of relevant memories (used for personalization)

**Logic Flow:**
1. Loads a prompt builder using the dispatcher, based on mode and memory presence
2. Constructs the prompt
3. Sends the prompt to the local Ollama instance
4. Returns:
    ```json
    {
        "status": "success",
        "reply": "<response from model>",
        "raw": { ...full LLM output... }
    }
    ```

---

## LLM Communication

- The LLM endpoint is defined by:
  - `OLLAMA_SERVER_URL = "http://localhost:11434/api/generate"`
  - `LLM_MODEL_NAME = "nemo"`

- Prompt requests are:
  - Non-streaming
  - Bounded by stop tokens: `["<|im_end|>", "[USER]"]`
  - Sent with a 30s timeout

- Responses include:
  - `reply`: model output (cleaned)
  - `model`: name of the model used
  - `raw`: unfiltered JSON response

---

## Configuration

Located in `proxy/config.py`:
```python
LLM_MODEL_NAME = "nemo"
OLLAMA_SERVER_URL = "http://localhost:11434/api/generate"
```

---

## Logging

- Prompt content is logged before being sent
- LLM response is logged after retrieval
- All errors are captured with a fallback reply indicating failure

---

## Notes

- The dispatcher function (`get_prompt_builder`) dynamically selects prompt styles.
- Currently only `/from/imessage` is active.
- Future versions may include additional endpoints such as `/from/email`, `/to/bluesky`, etc.
- This service is designed to support streaming and routing upgrades with minimal disruption.

