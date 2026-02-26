# Scheduler Microservice

Handles timed and recurring jobs via APScheduler with SQLite-backed persistence. The scheduler itself performs no business logic — it just fires HTTP callbacks when jobs are due. Brain creates jobs and receives the callbacks. Runs on `${SCHEDULER_PORT}`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/scheduler` | Create a new scheduled job |
| GET | `/scheduler` | List all jobs |
| DELETE | `/scheduler/{job_id}` | Delete a job |
| POST | `/scheduler/{job_id}/pause` | Pause a specific job |
| POST | `/scheduler/{job_id}/resume` | Resume a paused job |

## Job Creation

**POST /scheduler** with a `SchedulerJobRequest`:

```json
{
  "id": "optional-custom-id",
  "external_url": "http://brain:4207/scheduler/callback",
  "trigger": "cron",
  "hour": 9,
  "minute": 0,
  "day_of_week": "mon-fri",
  "metadata": { "action": "morning_summary" }
}
```

### Trigger Types

| Trigger | Required Fields | Description |
|---------|----------------|-------------|
| `date` | `run_date` (ISO datetime) | One-off execution at a specific time |
| `interval` | `interval_minutes` | Repeating every N minutes |
| `cron` | `hour`, `minute` (+ optional `day`, `day_of_week`) | Cron-like scheduling |

### Response (JobResponse)

```json
{
  "job_id": "abc-123",
  "external_url": "http://brain:4207/scheduler/callback",
  "next_run_time": "2026-02-27T09:00:00",
  "trigger": "cron",
  "metadata": { "action": "morning_summary" }
}
```

## How It Works

### Architecture

```
Brain: "Schedule a summary at 9 AM"
  → POST /scheduler (creates cron job, persists to SQLite)

APScheduler: (at 9 AM)
  → execute_job() fires
  → POST to external_url with metadata as JSON body

Brain: receives callback at /scheduler/callback
  → performs actual work (generate summary, send notification, etc.)
```

### Internals

- **APScheduler BackgroundScheduler** runs in a background thread
- **SQLAlchemyJobStore** persists jobs to `/shared/db/scheduler/scheduler.db`
- **ThreadPoolExecutor** with max 10 concurrent job executions
- `max_instances: 1` per job — prevents overlapping runs of the same job
- `coalesce: False` — missed jobs run immediately on recovery, don't skip
- Jobs survive container restarts (loaded from SQLite on startup)

### Job Execution (`util.py:execute_job`)

When a job fires, the scheduler POSTs the job's `metadata` dict as JSON to the `external_url`. There's no retry, no backoff — if the callback fails, it's logged and that's it.

## File Structure

```
app/
├── app.py                  # FastAPI setup, starts BackgroundScheduler
├── util.py                 # APScheduler config, execute_job() handler
├── routes/
│   └── scheduler.py        # All endpoint definitions
└── services/
    ├── add_job.py          # Job creation with trigger validation
    ├── list_jobs.py        # Job listing with trigger type detection
    ├── remove_job.py       # Job deletion
    ├── pause_job.py        # Job pausing
    └── resume_job.py       # Job resuming
```

## Dependencies

- **Brain service**: Creates jobs and receives callbacks
- **Shared models**: `SchedulerJobRequest`, `JobResponse`, `SchedulerCallbackRequest`
- **SQLite**: APScheduler job store at `shared/db/scheduler/scheduler.db`

## Known Issues and Recommendations

### Issues

1. **No timeout on callback requests** — `execute_job()` calls `requests.post()` with no timeout. A hung brain endpoint would block the executor thread indefinitely.

2. **No retry or error recovery** — Failed callbacks are logged and forgotten. No retry, no dead letter queue, no alerting.

3. **Callback payload mismatch** — `execute_job()` sends raw `metadata` as the POST body, but the `SchedulerCallbackRequest` model expects an `executed_at` timestamp field that's never populated.

4. **Trigger type detection is brittle** — `list_jobs.py` identifies trigger types by class name string matching (`trigger.__class__.__name__`). Should use `isinstance()`.

5. **No URL validation** — `external_url` accepts any string. Invalid URLs only fail at execution time.

6. **Global pause not implemented** — README previously claimed "pause/resume all jobs globally" but only per-job pause/resume exists.

7. **WAL mode not explicitly set** — SQLite database doesn't explicitly enable WAL mode.

### Recommendations

- Add `timeout=30` to the `requests.post()` call in `execute_job()`
- Add `executed_at` timestamp to the callback payload to match `SchedulerCallbackRequest`
- Add basic retry logic (1-2 retries with short backoff) for failed callbacks
- Validate `external_url` is a proper URL at job creation time
- Switch trigger type detection to `isinstance()` checks
