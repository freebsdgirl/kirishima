# Scheduler Microservice

Handles timed and recurring jobs for notification callbacks and summary generation. Built on APScheduler. Interface is intentionally minimal but a bit parameter-heavy.

## Features

- Schedules external callbacks (e.g., notifications, summaries)
- Supports 'date', 'interval', and 'cron' trigger types
- Flexible job metadata for arbitrary extension
- Pause/resume all jobs globally

## Job Attributes

- external_url (str): Endpoint to trigger when job runs
- trigger (str): Type of schedule ('date', 'interval', 'cron')
- run_date (str, optional): ISO datetime for one-off jobs
- interval_minutes (int, optional): Minutes between executions for interval jobs
- hour (int, optional): Hour for cron jobs
- minute (int, optional): Minute for cron jobs
- day (int, optional): Day of month for cron jobs
- day_of_week (str, optional): e.g., 'mon-fri' for cron jobs
- metadata (dict, optional): Extra data for downstream consumers

## Endpoints

- POST /jobs — Create a new scheduled job
- GET /jobs — List all jobs
- DELETE /jobs/{job_id} — Delete a job
- POST /pause — Pause all jobs
- POST /resume — Resume all jobs

## Notes

- Scheduling logic is on APScheduler; may migrate to ISO interval spec later.
- Most jobs are notification or summary callbacks—expand as needed.
- Yes, remembering the arguments is a nuisance. That’s what this README is for.