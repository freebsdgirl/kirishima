# Stickynotes Microservice

Persistent, context-aware reminders. Stickynotes are "naggy" by design — they surface during agent interactions, never as push notifications. The goal is gentle but persistent accountability: notes repeat every turn until resolved or snoozed. Runs on `${STICKYNOTES_PORT}`.

**Migration status**: A Google Tasks-backed replacement exists in `services/googleapi/` (see `README_TASKS.md`) with a different API surface (`/tasks/stickynotes`, `/tasks/due`, etc.). The migration was started but never completed — the brain tool still points at this standalone SQLite service. The two implementations have incompatible APIs.

**Current state**: Standalone SQLite service, no Google Tasks integration.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/create` | Create a sticky note (requires `text`, `due`; optional `periodicity`, `user_id`) |
| GET | `/list` | List all non-resolved notes for a user |
| GET | `/check` | Get notes that are currently due or overdue |
| GET | `/resolve/{note_id}` | Resolve a note (deletes one-time; advances recurring to next due date) |
| POST | `/snooze/{note_id}` | Snooze a note for a duration (`snooze_time` as ISO 8601 duration) |

## How It Works

### Lifecycle

1. **Create**: Note created with `text`, `due` datetime, optional `periodicity` (ISO 8601 interval like `R/P1D` for daily)
2. **Check**: On every agent interaction, brain calls `/check?user_id=...` to get due notes
3. **Surface**: Brain injects due notes as simulated tool calls into the conversation
4. **Action**: User resolves or snoozes via the `stickynotes` LLM tool
5. **Resolve**: One-time notes → status `resolved`, due cleared. Recurring notes → due advances by periodicity, stays `active`
6. **Snooze**: Due date set to `now + snooze_duration`, status → `snoozed`

### Integration with Brain

The brain tool (`app/tools/stickynotes.py`) calls this service at `http://stickynotes:4214`:
- **LLM tool actions**: `create`, `list`, `snooze`, `resolve` — called when the LLM decides to manage notes
- **Pre-injection** (`check_stickynotes()`): Called by multiturn before the LLM to surface due notes as simulated tool output

Notes are injected as `[assistant tool_call, tool result]` message pairs — the LLM sees them as if it had called the stickynotes tool itself.

## Database Schema

SQLite at `/shared/db/stickynotes/stickynotes.db` (WAL mode):

```
stickynotes (
    id          TEXT PK (UUID),
    text        TEXT NOT NULL,
    status      ENUM (active, snoozed, resolved),
    created_at  DATETIME WITH TZ,
    updated_at  DATETIME WITH TZ,
    user_id     TEXT (nullable, multi-tenant support),
    due         DATETIME WITH TZ,
    periodicity TEXT (nullable, ISO 8601 interval)
)
```

## Date/Time Formats

- **Due dates**: ISO 8601 naive datetime (e.g., `2026-02-27T09:00:00`)
- **Periodicity**: ISO 8601 repeating interval (e.g., `R/P1D` for daily, `R/P7D` for weekly)
- **Snooze duration**: ISO 8601 duration (e.g., `PT1H` for 1 hour, `P1D` for 1 day)

## File Structure

```
app/
├── app.py                          # FastAPI setup
├── schemas.py                      # Pydantic models (StickyNoteCreate, StickyNoteResponse, etc.)
├── setup.py                        # SQLAlchemy ORM + DB init
├── routes/
│   └── sticky_note_routes.py       # All endpoint definitions
└── services/
    ├── util.py                     # DB session management
    └── sticky_note_service.py      # Core business logic
```

## Known Issues and Recommendations

### Issues

1. **Missing `Query()` on snooze endpoint** — `snooze_time` parameter in `/snooze/{note_id}` isn't declared as `Query(...)`. FastAPI may misinterpret it as a path parameter. Brain tool sends it correctly as a query param, so it works, but direct API calls may fail.

2. **Timezone inconsistency** — Schema declares `DateTime(timezone=True)` but Pydantic model rejects timezone-aware datetimes. `datetime.now()` (naive) compared against tz-aware DB values. Works on most systems but fragile across timezone boundaries.

3. **Status comparison uses string literal** — `StickyNoteORM.status != "resolved"` instead of `StatusEnum.resolved`. Works but fragile.

4. **`/check` forces status to "active"** — Due notes returned with `status="active"` regardless of actual DB status. By design (snoozed notes past their snooze time should surface), but implicit.

5. **Dead dependency** — `dateutils` in requirements.txt but never imported. Service uses `isodate.parse_duration()` instead.

### Recommendations

- Add `Query(...)` to `snooze_time` parameter
- Standardize on naive datetimes throughout (remove `timezone=True` from schema)
- Use `StatusEnum` for comparisons
- Remove `dateutils` from requirements.txt
