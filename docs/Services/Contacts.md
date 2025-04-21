# 📇 Contacts

## Purpose

The Contacts microservice provides centralized identity resolution and contact management for the Kirishima system. It stores contacts with metadata, aliases, and cross-channel handles, enabling unified communication history and dispatch routing for all services.

## How It Works

- Built with FastAPI, the service initializes the app, adds request body caching middleware, and registers routers for all CRUD operations on contacts.
- All contact data is stored in a local SQLite database, with tables for contacts, aliases, and key-value fields.
- Endpoints allow for creating, retrieving, searching, updating (full and partial), and deleting contacts.
- Aliases and fields are validated for uniqueness and consistency.
- The service exposes a search endpoint for flexible lookups by alias or field value.
- Tracing is supported if enabled in the configuration.
- The included `scripts/contacts.py` CLI script allows users to list, add, modify, and delete contacts via the API.

## Port

- **4202** (default)

## Main Endpoints

- `POST /contact` – Create a new contact
- `GET /contacts` – List all contacts
- `GET /search` – Search for a contact by alias or field value
- `PUT /contact/{id}` – Replace a contact (full update)
- `PATCH /contact/{id}` – Partially update a contact (aliases, fields, or notes)
- `DELETE /contact/{id}` – Delete a contact

## Responsibilities

- Serve as the authoritative identity service for the system
- Map external IDs (email, Discord, iMessage, etc.) to internal user identity
- Enable Brain and other services to route messages and interpret summaries accurately
- Support aliasing for natural language identification (e.g., "mom", "boss")
- Provide a flexible, scriptable API for contact management

## Data Model

- `id`: UUID (unique identifier)
- `aliases`: List of alternative names or nicknames
- `fields`: List of key-value metadata (e.g., email, imessage, discord_id)
- `notes`: Optional user-defined notes

## Internal Details

- Uses SQLite for persistent storage
- All endpoints validate input and handle errors with structured responses
- Middleware is used for request body caching
- Tracing is enabled if configured

## CLI & Scripting

- The `scripts/contacts.py` script provides a command-line interface for managing contacts via the API, supporting list, add, modify, and delete operations with user-friendly prompts and output formatting.

## External Dependencies

- FastAPI
- SQLite (internal DB only)
- Used by Brain and other services needing identity context
