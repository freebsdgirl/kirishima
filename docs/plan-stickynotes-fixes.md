# Plan: Stickynotes Service Fixes

## Goal
Fix the bugs found during the doc review. The googleapi Tasks migration is abandoned — stickynotes stays standalone. The googleapi removal and doc cleanup are separate manual tasks.

## Fix 1: Missing Query() decorator on snooze endpoint

**File**: `services/stickynotes/app/routes/sticky_note_routes.py`

Find the `snooze_sticky_note` function signature and change:
```python
# Before
async def snooze_sticky_note(
    note_id: str,
    snooze_time: str,
    db: Session = Depends(get_db)
)

# After
from fastapi import Query

async def snooze_sticky_note(
    note_id: str,
    snooze_time: str = Query(..., description="ISO 8601 duration to snooze for, e.g. PT1H"),
    db: Session = Depends(get_db)
)
```

This ensures FastAPI correctly interprets `snooze_time` as a query parameter, not a path parameter.

## Fix 2: Remove dead `dateutils` dependency

**File**: `services/stickynotes/config/requirements.txt`

Remove the `dateutils` line. The service uses `isodate` for duration parsing, not `dateutils`.

## Fix 3: Use StatusEnum instead of string literal

**File**: `services/stickynotes/app/services/sticky_note_service.py`

Find:
```python
StickyNoteORM.status != "resolved"
```

Replace with:
```python
from app.schemas import StatusEnum
# ...
StickyNoteORM.status != StatusEnum.resolved.value
```

(Check the actual enum import path — it's likely in `schemas.py` based on the codebase structure.)

## Fix 4 (Optional): Backport RRULE support

If you want the richer recurrence from the Google Tasks version without the Google dependency:

1. Add `python-dateutil` to requirements.txt (it has `rrule` support)
2. Change `periodicity` field to accept either ISO 8601 intervals OR RRULE strings
3. In `resolve` logic, use `dateutil.rrule.rrulestr()` to compute next occurrence when RRULE is detected
4. Keep backward compat with existing ISO 8601 intervals (detect by prefix: RRULE starts with `FREQ=`, ISO starts with `R/`)

This is the one feature from the Google Tasks version worth keeping. Everything else (cloud sync, cross-platform) isn't critical for a personal assistant that surfaces notes in-conversation.

## What NOT to do

- Don't port the Google Tasks code into stickynotes — the APIs are incompatible and the standalone service works fine
- Don't add Google credentials to stickynotes
- The googleapi Tasks code (`services/googleapi/app/services/tasks/`) can be removed when you remove the googleapi service entirely — that's a separate manual task
