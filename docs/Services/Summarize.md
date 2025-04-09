# 📚 Summarize

## Purpose

The Summarize service handles long-form and short-form summarization for user communication across various platforms (iMessage, Discord, etc.). It abstracts over ChromaDB and acts as the primary interface for managing buffers and semantic summaries.

## Port

4203

## Endpoints

### `/buffer`

- `POST /buffer` – Add a message to the buffer
- `GET /buffer` – Retrieve all buffer entries
- `GET /buffer/{user_id}` – Retrieve buffer entries by user
- `DELETE /buffer/{user_id}` – Clear buffer for a user

### `/summary`

- `POST /summary` – Store a summary in [[ChromaDB]]
- `GET /summary/{id}` – Retrieve a summary by ID
- `GET /summary/user/{user_id}` – Get all summaries for a user
- `GET /summary/search` – Perform semantic + recency search
- `DELETE /summary/{id}` – Delete a summary by ID

### `/summarize_buffers`

- Triggers summarization of all current user buffers using local LLM and stores results

### `/context/{user_id}`

- Return merged summary and buffer entries for a user

## Responsibilities

- Aggregate short-form input for scheduled summarization
- Route summarization prompts to Ollama
- Store and score summaries using ChromaDB
- Clear buffer once summarized
- Provide unified context for prompt injection

## Design Philosophy & Summary Types

The service is designed to abstract and normalize message data from multiple platforms. It stores, summarizes, and surfaces conversational context based on the format and type of message input:

### 1. Long-Form Communication

- Single messages with rich context
- Summarized individually on receipt
- Stored immediately in ChromaDB
- Associated with contact identity via Contacts service

### 2. Short-Form Communication

- Rapid-fire conversational input
- Messages written to a rolling buffer tied to `user_id` and `platform`
- Summarized on a schedule (Stage 1/2/3 via Scheduler + Brain)
- Summaries stored in ChromaDB; buffers are cleared after summarization

Buffer entries are retained per-user and per-platform to support platform-specific summarization and future multi-channel aggregation.

## Summary Workflow

1. Brain or Scheduler hits `POST /summarize_buffers`
2. Service pulls buffer entries grouped by user
3. Sends grouped text to local LLM via ollama
4. Saves resulting summary to `/summary`
5. Clears that user's buffer via `DELETE /buffer/{user_id}`

Summaries are timestamped and semantically searchable. The scoring function balances semantic relevance and recency:

```python
combined_score = (semantic_score * 0.7) + (recency_score * 0.3)
```

## External Dependencies

- ollama
- ChromaDB API
- Brain (sends summarization triggers)
- Scheduler (triggers timed summaries)
- Contacts service (for resolving user identity)
