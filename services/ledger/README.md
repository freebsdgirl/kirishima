# Ledger Microservice

A persistent message ledger for 1-on-1 conversations, storing message buffers across platforms in SQLite.

## Features

- Stores all user, assistant, system, and tool messages with full metadata
- Deduplication of user and assistant messages
- Handles consecutive user messages (e.g., after server errors)
- Edits assistant messages in place if content changes
- Appends new messages, ensuring the buffer always starts with a user message
- Filters out tool and assistant messages with empty content

## Endpoints

- `GET /user/{user_id}/messages`  
  Retrieve messages for a user, optionally filtered by time period (`night`, `morning`, `afternoon`, `evening`, `day`) and date
- `GET /active`  
  List user IDs present in the database
- `DELETE /user/{user_id}`  
  Delete all messages for a user, or only those in a specified period and date; keeps 10 most recent by default
- `POST /user/{user_id}/sync`  
  Sync a user’s message buffer with deduplication, edit detection, and proper ordering

## Schema

- Table: `user_messages` (table name should move to config.json)
    - user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, timestamps

## Notes

- Uses SQLite for all persistence
- Sync endpoint is responsible for all the pain: deduplication, handling assistant edits, consecutive user messages, and ordering
- Summaries used to be managed here (now removed); can be re-added if needed for chromadb migration
