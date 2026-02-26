# Plan: Scheduler Brain Tool

## Goal
Add a `scheduler` brain tool so the LLM can create/list/delete/pause/resume scheduled jobs via natural language instead of manual curl commands.

## Prerequisites
- Familiarize with the existing tool pattern: `services/brain/app/tools/stickynotes.py` is the closest model
- Read `services/brain/app/tools/base.py` for the `@tool` decorator
- Read `services/scheduler/README.md` for the scheduler API

## Step 1: Create the tool file

Create `services/brain/app/tools/scheduler.py`:

```python
@tool(
    name="scheduler",
    description="Manage scheduled jobs - create recurring or one-time scheduled tasks, list existing jobs, delete jobs, or pause/resume them",
    persistent=True,
    always=False,        # Routed, not always-on (only relevant when user is talking about scheduling)
    clients=["internal"],
    guidance="Use ISO 8601 datetime for run_date (e.g. 2026-02-27T09:00:00). For cron jobs, specify hour (0-23) and minute (0-59), optionally day_of_week (e.g. 'mon-fri'). For interval jobs, specify interval_minutes. The external_url for brain callbacks is http://brain:{BRAIN_PORT}/scheduler/callback.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "delete", "pause", "resume"],
                "description": "The action to perform"
            },
            "trigger": {
                "type": "string",
                "enum": ["date", "interval", "cron"],
                "description": "Trigger type (required for create)"
            },
            "run_date": {
                "type": "string",
                "description": "ISO 8601 datetime for one-off jobs (required if trigger=date)"
            },
            "interval_minutes": {
                "type": "integer",
                "description": "Minutes between executions (required if trigger=interval)"
            },
            "hour": {
                "type": "integer",
                "description": "Hour for cron jobs (0-23)"
            },
            "minute": {
                "type": "integer",
                "description": "Minute for cron jobs (0-59)"
            },
            "day_of_week": {
                "type": "string",
                "description": "Day(s) of week for cron jobs (e.g. 'mon-fri', 'sat,sun')"
            },
            "external_url": {
                "type": "string",
                "description": "URL to call when job fires. Defaults to brain scheduler callback."
            },
            "metadata": {
                "type": "object",
                "description": "Arbitrary metadata passed to the callback when job fires"
            },
            "job_id": {
                "type": "string",
                "description": "Job ID (required for delete, pause, resume)"
            }
        },
        "required": ["action"]
    },
)
async def scheduler(parameters: dict) -> ToolResponse:
```

### Action implementations:

- **create**: POST to `http://scheduler:{SCHEDULER_PORT}/scheduler` with trigger params + metadata. Default `external_url` to `http://brain:{BRAIN_PORT}/scheduler/callback` if not provided.
- **list**: GET `http://scheduler:{SCHEDULER_PORT}/scheduler`, return formatted job list
- **delete**: DELETE `http://scheduler:{SCHEDULER_PORT}/scheduler/{job_id}`
- **pause**: POST `http://scheduler:{SCHEDULER_PORT}/scheduler/{job_id}/pause`
- **resume**: POST `http://scheduler:{SCHEDULER_PORT}/scheduler/{job_id}/resume`

Use `httpx.AsyncClient` with timeout, same pattern as stickynotes.py.

## Step 2: Fix scheduler callback payload

In `services/scheduler/app/util.py`, update `execute_job()`:

```python
def execute_job(external_url: str, metadata: Dict[str, Any]):
    try:
        payload = {
            "metadata": metadata,
            "executed_at": datetime.utcnow().isoformat() + "Z"
        }
        response = requests.post(external_url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Job executed successfully, response: {response.text}")
    except Exception as e:
        logger.error(f"Error executing job: {e}")
```

Two changes:
1. Add `executed_at` timestamp to match `SchedulerCallbackRequest` model
2. Add `timeout=30` to prevent hanging

## Step 3: Add tool to router catalog

No manual step needed — the `@tool` decorator with `always=False` automatically makes it available to the tool router. The router will include it when the user's message is about scheduling.

## Step 4: Test

1. Start a conversation and say "Schedule a daily check-in at 9 AM on weekdays"
2. Verify the LLM creates a cron job via the tool
3. Say "List my scheduled jobs" — verify list action works
4. Say "Delete the morning check-in" — verify delete works
5. Check scheduler logs to confirm job creation/deletion

## Notes

- The tool is `always=False` (routed) because scheduling is infrequent — no need to send the tool definition on every single request
- `external_url` defaults to brain's scheduler callback but can be overridden for flexibility
- The `metadata` field is where the LLM puts context about what the job should do when it fires (e.g., `{"action": "morning_summary"}`)
