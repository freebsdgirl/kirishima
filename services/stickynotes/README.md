# Stickynotes

Persistent, context-aware reminders for personal AI agents. Stickynotes are “naggy” by design: they only surface during direct agent interactions, never as unsolicited notifications. The goal is to gently but persistently remind the user of tasks, habits, or recurring events—without intruding on their attention outside of chat.

## Features

- **Persistent Reminders**: Stickynotes repeat every turn until resolved or snoozed.
- **Context-Only Surfacing**: Reminders only appear when the user interacts with the agent—not as push notifications.
- **One-Time and Recurring**: Supports both one-off notes and periodic reminders (hourly, daily, weekly, monthly).
- **Snooze and Resolve**: Temporarily suppress a note (snooze) or resolve it. Recurring notes “sleep” until the next scheduled trigger; one-time notes are deleted on resolve.
- **API-Driven**: Exposed as a FastAPI + Uvicorn microservice, integrated with the “brain” orchestrator.
- **SQLite Storage**: All stickynotes data is stored in `/shared/db/stickynotes.db`.

## API Actions

- `POST /create`: Add a stickynote.
  - Required: `note` (text)
  - Optional: `periodic` (hourly|daily|weekly|monthly), `date` (ISO timestamp)
- `GET /resolve/{note_id}`: Remove a stickynote (or set recurring note to sleep until next trigger).
  - Required: `note_id` (path parameter)
- `POST /snooze/{note_id}`: Temporarily suppress a stickynote.
  - Required: `note_id` (path parameter), `date` (ISO timestamp until which to snooze)
- `GET /list`: Retrieve all stickynotes regardless of status.
- `GET /check`: Get all active stickynotes that should be displayed to the user.

## Workflow

- On every agent interaction, the brain hits the stickynotes service.
- API returns an array of active stickynote metadata (or empty array if none).
- Agent injects stickynotes as simulated tool output into the conversation, and logs them to ledger.
- Stickynotes repeat each turn until resolved or snoozed.
- No notifications are pushed outside of chat context.

## Storage

- SQLite DB at `/shared/db/stickynotes.db`.
- Each stickynote stores: id, note, periodic (nullable), date (next due or snooze-until), created_at, updated_at, and status.

## Design Principles

- Never intrusive—no push, only gentle persistence on interaction.
- Handles both recurring and one-off reminders.
- Simple, transparent API that’s easy to extend.
- Avoids silent errors or lost reminders by making every note visible until actioned.
