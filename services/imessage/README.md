# iMessage Microservice

Integrates with BlueBubbles (running on an iMac) to send and receive iMessages via the BlueBubbles API.

## Features

- Sends iMessages to recipients using BlueBubbles API
- Receives incoming iMessage webhooks from BlueBubbles and filters out everything but new, non-self messages
- Forwards incoming messages to the core brain service for automated replies (should use /chat/completions via proxy)
- Handles chat creation if it doesn’t exist
- Logs, traces, and applies request body caching

## Endpoints

- `POST /send` — Send an iMessage to a specified recipient
- `POST /recv` — Receive/process incoming iMessage webhooks from BlueBubbles

## Configuration

- Environment variables (default values in parentheses):
    - `BLUEBUBBLES_HOST`: Hostname for BlueBubbles server (`localhost`)
    - `BLUEBUBBLES_PORT`: Port for BlueBubbles server (`3000`)
    - `BLUEBUBBLES_PASSWORD`: Password for BlueBubbles (`bluebubbles`)
- Plan: move config to `config.json` in the future

## How It Works

- Only processes webhook payloads for new messages where `isFromMe` is not set
- Messages are forwarded to the brain service, which should now use `/chat/completions` for LLM responses
- Contact/user_id resolution is done via the contacts microservice
- If a chat doesn’t exist, it will be created automatically when sending

## Maintenance Notes

- Refactor all message routing to use `/chat/completions` via the proxy
- Watch out for BlueBubbles webhook spam; logic must stay robust