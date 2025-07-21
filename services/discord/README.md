# Di## Features

- **POST /dm**: Send direct messages via FastAPI endpoint
- Handles direct message events, ignores bots, and manages command processing
- Forwards Discord messages to the core "brain" service via HTTP (use /chat/completions endpoint via the proxy)
- Supports user registration and contact linking, syncing Discord users to the contacts microservice
- Includes robust error logging and handlingicroservice

This microservice bridges Discord direct messaging with the Kirishima system. It exposes FastAPI endpoints and uses a Discord.py bot to process, send, and relay Discord DMs.

## Features

- Sends DMs via FastAPI POST endpoints
- Handles direct message events, ignores bots, and manages command processing
- Forwards Discord messages to the core “brain” service via HTTP (use /chat/completions endpoint via the proxy)
- Supports user registration and contact linking, syncing Discord users to the contacts microservice
- Includes robust error logging and handling

## Registration

- Users can register or update their contact info via DM commands (e.g., `register`)
- Registration is only available in DMs and will either create a new contact or update an existing one, syncing Discord info to the contacts microservice

## Integration

- All message forwarding and response logic must use the /chat/completions endpoint via the proxy
- Utility functions handle Discord/contact lookups and synchronization

## Dependencies

- FastAPI
- Discord.py
- httpx
- Shared config and logging modules
- Contacts microservice

## Maintenance Notes

- All legacy endpoints must be refactored to use the proxy API
- Confirm all contact sync operations are functional after any API or structure changes