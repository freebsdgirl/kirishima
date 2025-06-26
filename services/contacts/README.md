# Contacts Microservice

The contacts microservice manages contact information in a SQLite database. It’s designed primarily for single-user operation (Randi), but supports additional contacts for notification routing and future integrations.

## Features

- Stores contacts with arbitrary keys, including:
    - `imessage`
    - `discord`
    - `discord_id`
    - `email`
    - `aliases`
    - `notes`
- Allows storage and retrieval of any other fields as needed.

## Usage

- **Single-User Context:**  
  When running under OpenWebUI (no user context), the contact with the alias `@ADMIN` is assumed to be the current user.  
  **System integrity depends on always having a contact with the `@ADMIN` alias.**

- **Notifications & Integrations:**  
  Additional contacts can be added for use in other microservices (e.g., “email my mom”).

- **CLI Management:**  
  Use the CLI script in `/scripts` to add, edit, or remove contacts.

## Requirements

- SQLite database with at least one contact having the alias `@ADMIN`.

## Example

```json
{
  "aliases": ["@ADMIN", "Randi"],
  "imessage": "+15555555555",
  "discord": "freebsdgirl#1234",
  "discord_id": "1234567890",
  "email": "randi@example.com",
  "notes": "Primary user. Required for system operation."
}
