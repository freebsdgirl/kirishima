# Ledger Microservice

Persistent data store for all conversational data. Manages message buffers, memories, topics, summaries, and the context heatmap system. Everything is SQLite with WAL mode. Runs on `${LEDGER_PORT}`.

## Endpoints

### Message Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/user/{user_id}/messages` | Get messages (filter by period/date/timestamps) |
| GET | `/user/stream` | Stream new message rows live via SSE (single-user config user_id) |
| GET | `/user/{user_id}/messages/last` | Last message timestamp |
| GET | `/user/{user_id}/messages/untagged` | Messages without topic assignment |
| PATCH | `/user/{user_id}/messages/{row_id}` | Edit one message row's content (user/assistant only) |
| DELETE | `/user/{user_id}/messages/from/{row_id}` | Delete all rows from row_id onward (inclusive) |
| POST | `/user/{user_id}/sync` | Complex message buffer synchronization |
| DELETE | `/user/{user_id}` | Delete messages (filter by period/date) |
| GET | `/user/active` | List all active user IDs |

### Sync Operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sync/user` | User message sync |
| POST | `/sync/assistant` | Assistant message sync |
| POST | `/sync/tool` | Tool call sync |
| GET | `/sync/get` | Get sync buffer (token-limited) |

### Memory Operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/memories` | Create memory (requires keywords; category optional) |
| GET | `/memories` | List memories (paginated) |
| GET | `/memories/by-id/{id}` | Get memory with full details |
| PATCH | `/memories/by-id/{id}` | Update memory content/keywords/category |
| DELETE | `/memories/by-id/{id}` | Delete memory (cascades) |
| PATCH | `/memories/by-id/{id}/topic` | Assign topic to memory |
| GET | `/memories/by-topic/{topic_id}` | Get memories by topic |
| GET | `/memories/_search` | Advanced multi-parameter search |
| POST | `/memories/_scan` | Identify and assign topics for messages via LLM |
| GET | `/memories/_dedup` | Legacy deduplication |
| GET | `/memories/_dedup_semantic` | Semantic dedup (timeframe or keyword grouping) |
| POST | `/memories/_dedup_topic_based` | Two-phase topic consolidation + memory dedup |

### Topic Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/topics` | List all topics |
| POST | `/topics` | Create topic (dedup by name) |
| GET | `/topics/{id}` | Get topic details |
| DELETE | `/topics/{id}` | Delete topic (cascades) |
| PATCH | `/topics/{id}` | Assign topic to messages in timeframe |
| GET | `/topics/{id}/messages` | Get messages for topic |
| GET | `/topics/_recent` | Recent topics |
| POST | `/topics/_by-timeframe` | Topics with messages in time range |
| POST | `/topics/_dedup_semantic` | Semantic topic deduplication via DBSCAN + LLM |

### Summary Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/summary` | Retrieve summaries (filter by type, time, keywords) |
| POST | `/summary` | Create summary record |
| DELETE | `/summary` | Delete summaries |
| POST | `/summary/create` | Generate summaries from message data |

### Context/Heatmap Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/context/` | Get top contextually relevant memories |
| POST | `/context/update_heatmap` | Update keyword weights, rescore all memories |
| GET | `/context/top_memories` | Top-scored memories with scores |
| GET | `/context/keyword_scores` | Current heatmap state |

## Database Schema

### Tables

**`user_messages`** — Message buffer
```
id, user_id, platform, platform_msg_id, role, content, model,
tool_calls (JSON), function_call (JSON), tool_call_id,
topic_id (FK→topics), created_at, updated_at
```

**`memories`** — Long-term knowledge store
```
id (UUID), memory (text), created_at, access_count, last_accessed, reviewed
```

**`memory_tags`** — Keywords per memory (many-to-many)
```
memory_id (FK→memories), tag (lowercase), PK(memory_id, tag)
```

**`memory_category`** — Category per memory
```
memory_id (FK→memories), category, PK(memory_id, category)
```
Allowed categories: Health, Career, Family, Personal, Technical Projects, Social, Finance, Self-care, Environment, Hobbies, Admin, Philosophy

**`memory_topics`** — Memory-to-topic links
```
memory_id (FK→memories), topic_id (FK→topics), PK(memory_id, topic_id)
```

**`topics`** — Conversation topics
```
id (UUID), name, description, created_at
```

**`summaries`** — Temporal summaries
```
id (UUID), summary (text), timestamp_begin, timestamp_end,
summary_type (morning|afternoon|evening|night|daily|weekly|monthly)
```

**`heatmap_score`** — Keyword relevance tracking
```
keyword (PK), score (0.1–2.0), last_updated
```

**`heatmap_memories`** — Cached memory scores from heatmap
```
memory_id (PK, FK→memories), score, last_updated
```

All tables: WAL mode, foreign keys enabled, appropriate indexes.

## Key Systems

### Message Sync

The sync system (`POST /user/{user_id}/sync`) handles complex message buffer management:

- **Consecutive user messages**: After server errors, detects and deduplicates
- **Non-API fast path**: Discord/iMessage messages appended directly
- **API dedup logic**: Handles identical user messages, assistant edits (in-place update), and fallback append
- **Buffer limiting**: Returns last N messages (configured by `ledger.turns`, default 15), ensures first message is always `user` role
- **Field preservation**: tool_calls, function_call, tool_call_id maintained through sync

### Memory System

**Creation**: Memory + keywords + optional category → UUID-based storage

**Search** (`GET /memories/_search`): Multi-parameter AND logic:
- `keywords` with progressive fallback (reduces `min_keywords` if no results)
- `category` exact match
- `topic_id` via memory_topics
- `created_after`/`created_before` time range
- `memory_id` direct lookup (bypasses all filters)
- Updates `access_count` and `last_accessed` on retrieval

**Scanning** (`POST /memories/_scan`): Topic assignment pass over conversations:
- Processes oldest untagged messages in batches of 30
- LLM analyzes conversation → returns topic windows as JSON
- Creates topics and assigns them to messages
- Does not create memories automatically

**Deduplication**: Three approaches:
- `_dedup_semantic`: Groups by timeframe or keyword overlap → LLM decides merges
- `_dedup_topic_based`: Two-phase — DBSCAN topic clustering + timeframe memory chunking → LLM merges
- `_dedup` (legacy): Various strategies

### Context Heatmap

Dynamic keyword relevance tracking for conversation-aware memory retrieval:

**Scoring mechanics:**
- Keywords weighted as high (1.0), medium (0.7), or low (0.5)
- **Reinforcement**: Same-weight keywords get 10% boost on repeat mention
- **Adjustment**: Different-weight keywords shift 10% toward new target
- **Decay**: Unused keywords lose 0.08 per cycle
- **Removal**: Below 0.1 score → deleted
- **Clamping**: Scores bounded 0.1–2.0

**Memory scoring**: Sum of matching keyword scores per memory. All memories rescored on every heatmap update. Cached in `heatmap_memories` for fast retrieval.

### Summary System

Time-period summaries of conversations:
- **Periods**: morning (06-11), afternoon (12-17), evening (18-23), night (00-05)
- **Aggregates**: daily, weekly, monthly
- Generated from message data via LLM prompts

## File Structure

```
app/
├── app.py                          # FastAPI setup
├── setup.py                        # Schema initialization
├── util.py                         # DB connection helper
├── routes/
│   ├── user.py                     # Message endpoints
│   ├── sync.py                     # Sync endpoints
│   ├── memory.py                   # Memory CRUD + search/scan/dedup
│   ├── topic.py                    # Topic CRUD + dedup
│   ├── context.py                  # Heatmap endpoints
│   └── summary.py                  # Summary endpoints
└── services/
    ├── user/                       # Message operations, sync logic
    ├── memory/                     # Memory CRUD, search, scan, dedup (24 files)
    ├── topic/                      # Topic operations (9 files)
    ├── context/
    │   └── heatmap.py              # Heatmap scoring engine
    └── summary/                    # Summary generation (7 files)
```

## Integration

| Service | How It Uses Ledger |
|---------|-------------------|
| **Brain** | Message sync, memory search, heatmap updates, summaries |
| **API** (via brain) | Indirect — all messages flow through brain to ledger |

Ledger also calls the API/proxy for LLM completions during memory scanning and deduplication operations.

## Configuration

```json
{
    "db": { "ledger": "/path/to/ledger.db" },
    "ledger": { "turns": 15 },
    "timeout": 120,
    "tracing_enabled": false
}
```

## Known Issues and Recommendations

### Issues

1. **Commented-out background tasks** — Multiple references to `background_tasks.add_task(create_summaries, ...)` in sync code, all commented out. Either complete or remove.

2. **Tool sync incomplete** — `sync/tool.py` defines structure but minimal processing. Tool-generated insights aren't integrated with memory/topic systems.

3. **Assistant sync hardcodes user_id from config** — `sync/assistant.py:22` reads user_id from config instead of accepting from request. Only works for single-user.

4. **Heatmap rescoring is synchronous** — `_recalculate_memory_scores()` blocks on every heatmap update. Could be slow with many memories.

5. **Memory access_count inconsistent** — Only updated during search operations. Direct GET by ID doesn't update it.

6. **Summary keyword search not implemented** — Route accepts `keywords` parameter but silently ignores it.

7. **No connection pooling** — New SQLite connection per operation. Fine for current scale but not ideal.

8. **No transaction wrapping on scan operations** — Memory scan creates topics, assigns messages, creates memories without explicit transactions. Partial failures leave inconsistent state.

9. **Period range uses magic numbers** — Morning=6-11, afternoon=12-17, etc. hardcoded. Should be named constants.

10. **No rate limiting on expensive operations** — Memory scan, dedup, semantic operations consume LLM tokens with no limits.

11. **Heatmap tolerance check is arbitrary** — `abs(current_score - base_score) < 0.2` for "same weight" detection. Magic number with unclear semantics.

### Recommendations

- Wrap scan/dedup operations in explicit transactions
- Move heatmap rescoring to background task
- Implement summary keyword filtering (feature is plumbed but non-functional)
- Make time period boundaries configurable constants
- Track access_count consistently across all retrieval paths
- Add rate limiting or token budgets for LLM-consuming operations
