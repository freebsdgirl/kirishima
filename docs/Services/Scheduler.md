# ⏱ Scheduler

## Purpose

Provides persistent, API-accessible time-based job scheduling using APScheduler with a SQLAlchemy job store. This service accepts requests to schedule or manage jobs and calls external URLs (typically Brain) with job metadata at the time of execution.

## Port

4201

## Endpoints

### Job Lifecycle

- `POST /jobs` – Create a new scheduled job (date or interval)
- `GET /jobs` – List all active jobs
- `DELETE /jobs/{job_id}` – Cancel a job
- `POST /jobs/{job_id}/pause` – Temporarily disable a job
- `POST /jobs/{job_id}/resume` – Resume a paused job

## JobRequest Schema

- `external_url` – URL to POST to when job is triggered
- `trigger` – `"date"` or `"interval"`
- `run_date` – For one-time jobs (UTC datetime)
- `interval_minutes` – For repeating jobs
- `metadata` – Arbitrary dictionary sent to the trigger endpoint

## Internal Behavior

- Jobs are stored in a SQLite database (`db/jobs.db`)
- APScheduler is configured with:
  - SQLAlchemyJobStore
  - ThreadPoolExecutor (max 10 workers)
  - `coalesce=False`, `max_instances=1`
- When a job fires, a `POST` is sent to `external_url` with:
  
  ```json
  {
    "metadata": { ... },
    "executed_at": "2025-04-05T12:34:56Z"
  }
  ```

## Responsibilities

- Keep accurate and persistent job state
- Trigger external execution (via HTTP POST) on schedule
- Report job status, metadata, and runtime state
- Support pause/resume/delete behavior

## Design Principle

> "Scheduler is the wristwatch. The Brain sets it, but the watch tells time and rings the alarm."

This service does **not** perform logic or make decisions. It only manages **when** things happen, not **what** should happen.

## External Dependencies

- SQLite (via SQLAlchemy)
- Brain service (as primary trigger target)
- Logging via Graylog-compatible system
