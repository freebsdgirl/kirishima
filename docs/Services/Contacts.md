
# 📇 Contacts

## Purpose
Provides centralized identity resolution across platforms. Stores contacts with metadata, aliases, and cross-channel handles for unifying communication history and dispatch routing.

## Port
4202

## Endpoints

- `POST /contact` – Create a new contact
- `GET /contact/{id}` – Retrieve contact by ID
- `GET /contact` – List or search contacts
- `PATCH /contact/{id}` – Partially update a contact
- `DELETE /contact/{id}` – Delete a contact

## Responsibilities
- Serve as the authoritative identity service
- Map external IDs (Email, Discord, [[iMessage]]) to internal user identity
- Enable [[Brain]] to route messages and interpret summaries accurately
- Support aliasing for natural language identification ("mom", "boss", etc.)

## Data Model
- `id`: UUID
- `name`: Display name
- `aliases`: List of nicknames or short refs
- `fields`: Key-value metadata (e.g., discord_id, email)
- `notes`: Arbitrary user-defined metadata

## External Dependencies
- SQLite (internal DB only)
- Queried by [[Brain]] and other services needing identity context
