
# 📚 Ledger & Summary Service

## Purpose

The **Ledger & Summary** service persists all conversational data and manages multi‑level summaries for both 1‑on‑1 chats and Discord group channels.

* **Ledger layer** – authoritative buffer of raw messages (per‑user and per‑conversation).
* **User summaries** – token‑based, multi‑level compression (`level 1 … N`).
* **Conversation summaries** – time‑based rollups (`daily → weekly → monthly`).

Everything lives in SQLite for now; HTTP endpoints make it trivial to split into micro‑services later.

---

## Ports

| Service | Port |
|---------|------|
| Ledger API (buffers + summaries) | **4203** |

---

## Config Vars (`app.config`)

| Var | Description | Default |
|-----|-------------|---------|
| `user_chunk_size` | Max tokens to feed into one user summary chunk | **512** |
| `user_chunk_at` | Buffer must hit this many tokens before summarising | **1024** |
| `user_summary_chunk_size` | How many `level n` summaries to combine | **3** |
| `user_summary_chunk_at` | Combine once ≥ this many `level n` summaries exist | **5** |
| `user_summary_tokens` | Target token budget for each summary | **128** |
| `conversation_buffer_keep` | Minimum newest messages to keep in convo buffer | *(config)* |

---

## Endpoint Reference

### User Buffer (1‑on‑1)

| Method | Path | Body Model | Response |
|--------|------|-----------|----------|
| POST | `/ledger/user/{user_id}/sync` | `List[RawUserMessage]` | `List[CanonicalUserMessage]` |
| GET | `/ledger/user/{user_id}/messages` | – | `List[CanonicalUserMessage]` |
| DELETE | `/ledger/user/{user_id}/before/{id}` | – | `DeleteSummary` |
| DELETE | `/ledger/user/{user_id}` | – | `DeleteSummary` |

### Conversation Buffer (Discord)

| Method | Path | Body Model | Response |
|--------|------|-----------|----------|
| POST | `/ledger/conversation/{conversation_id}/sync` | `List[RawConversationMessage]` | `List[CanonicalConversationMessage]` |
| GET | `/ledger/conversation/{conversation_id}/messages` | – | `List[CanonicalConversationMessage]` |
| DELETE | `/ledger/conversation/{conversation_id}/before/{id}` | – | `DeleteSummary` |
| DELETE | `/ledger/conversation/{conversation_id}` | – | `DeleteSummary` |

### User Summaries

| Method | Path | Body Model | Response |
|--------|------|-----------|----------|
| GET | `/summaries/user/{user_id}?limit=&level=` | – | `UserSummaryList` |
| DELETE | `/summaries/user/{user_id}` | `DeleteRequest` | `DeleteSummary` |
| POST | `/summaries/user/{user_id}/create` | – | `{status}` (201) |

### Conversation Summaries

| Method | Path | Body Model | Response |
|--------|------|-----------|----------|
| GET | `/summaries/conversation/{conversation_id}?period=&limit=` | – | `ConversationSummaryList` |
| POST | `/summaries/conversation/{conversation_id}/daily/create` | – | `{status}` (201) |
| POST | `/summaries/conversation/{conversation_id}/weekly/create` | – | `{status}` (201) |
| POST | `/summaries/conversation/{conversation_id}/monthly/create` | – | `{status}` (201) |

---

## Workflows

### ⏩ User Compression

1. Scheduler hits `POST /summaries/user/{user_id}/create`.
2. Ledger fetches buffer: `/ledger/user/{user_id}/messages`.
3. If tokens ≥ `user_chunk_at`, oldest ≤ `user_chunk_size` tokens are summarised via Proxy.
4. `level 1` summary stored; buffer entries ≤ *last id* are pruned.
5. Old `level n` summaries are recursively compressed into `level n+1` until each level has `< user_summary_chunk_at` items (max level 10).

### 🗓️ Conversation Time‑Rollups

* **Daily** – summarises the 48‑24 h window, prunes messages older than 24 h (leave last `conversation_buffer_keep`).
* **Weekly** – combines the previous seven daily summaries.
* **Monthly** – combines the previous four weekly summaries.
* Summaries are **never deleted**.

---

## DB Tables

| Table | Purpose |
|-------|---------|
| `user_messages` | Raw 1‑on‑1 buffer |
| `conversation_messages` | Raw Discord buffer |
| `user_summaries` | Multi‑level user summaries |
| `conversation_summaries` | Daily/weekly/monthly convo summaries |

---

## External Dependencies

* **httpx** – intra‑service requests  
* **tiktoken** – approximate GPT‑2 token counting  
* **Proxy summariser (port 4205)** – LLM summarization

---

_Last updated: 2025-04-22 14:50 UTC_
