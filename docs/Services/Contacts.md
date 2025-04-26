# 📇 Contacts

## Purpose

Provides centralized identity resolution across platforms. Stores contacts with metadata, aliases, and cross-channel handles for unifying communication history and dispatch routing. The Contacts service is the authoritative source for user identity, supporting natural language aliasing and metadata for robust, cross-channel communication.

## Port

4202

## Endpoints

- `POST /contact` – Create a new contact. Accepts aliases, fields (key-value metadata), and notes. Returns the created contact object.
- `GET /contact/{id}` – Retrieve a contact by its unique ID. Returns the full contact object, including all aliases and fields.
- `GET /contact` – List all contacts or search by alias/field. Returns a list of all contacts with their metadata.
- `PATCH /contact/{id}` – Partially update a contact. Only the provided fields/aliases/notes are updated; others are preserved. Setting a field value to an empty string deletes that field.
- `DELETE /contact/{id}` – Delete a contact and all associated aliases/fields.

## Responsibilities

- Serve as the authoritative identity service for the system.
- Map external IDs (Email, Discord, iMessage, etc.) to internal user identity.
- Enable the Brain service to route messages and interpret summaries accurately.
- Support aliasing for natural language identification (e.g., "mom", "boss", "@ADMIN").
- Enforce business rules, such as the uniqueness of the `@ADMIN` alias (only one contact can have this alias at a time).
- Provide robust error handling and logging for all operations.

## Data Model

- `id`: UUID (primary key, unique per contact)
- `aliases`: List of nicknames or short refs (unique per contact; `@ADMIN` is globally unique)
- `fields`: Key-value metadata (e.g., discord_id, email, imessage; unique key per contact)
- `notes`: Arbitrary user-defined metadata (freeform text)

### Database Schema (SQLite)

```sql
CREATE TABLE contacts (
    id TEXT PRIMARY KEY,
    notes TEXT
);

CREATE TABLE aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    UNIQUE(contact_id, alias),
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

CREATE TABLE fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(contact_id, key),
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);
```

- **ON DELETE CASCADE** ensures aliases and fields are deleted when a contact is removed.
- **UNIQUE(contact_id, alias)** and **UNIQUE(contact_id, key)** prevent duplicate aliases/fields for a contact.
- **@ADMIN alias** is enforced as globally unique by application logic (409 Conflict if violated).

## API Behavior & Business Logic

- **Partial Updates:** PATCH only updates provided fields/aliases/notes. Setting a field value to an empty string deletes that field.
- **@ADMIN Alias:** Only one contact can have the `@ADMIN` alias. Attempts to assign it to another contact result in a 409 Conflict error.
- **Foreign Key Integrity:** All deletions cascade to aliases and fields.
- **Automatic DB Initialization:** On startup, the service checks for the existence of the database and tables, and creates them if missing, using the schema above.
- **Logging:** All operations are logged for traceability and debugging.

## Example Usage

- **Add a Contact:**
  ```bash
  python scripts/contacts.py add --aliases "Alice" --email "alice@example.com" --notes "VIP"
  ```
- **List Contacts:**
  ```bash
  python scripts/contacts.py list
  ```
- **Modify a Contact:**
  ```bash
  python scripts/contacts.py modify <contact_id> --email "new@email.com"
  ```
- **Delete a Contact:**
  ```bash
  python scripts/contacts.py delete <contact_id>
  ```

## External Dependencies

- SQLite (internal DB only; automatically initialized if missing)
- Queried by Brain and other services needing identity context

## Extending the Service

- Add new fields to the `fields` table as needed (no schema change required).
- Add new endpoints or business logic in the FastAPI app and supporting modules.
- Update the schema in `sql/contacts.sql` and initialization logic as needed.

---

For more details, see the code in `services/contacts/app/` and the CLI in `scripts/contacts.py`.
