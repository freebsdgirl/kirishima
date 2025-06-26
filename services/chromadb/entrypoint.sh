#!/bin/sh
set -e

exec uvicorn app.app:app --host 0.0.0.0 --port ${SERVICE_PORT} --reload
