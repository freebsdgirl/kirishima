# Contacts Microservice

Manages contact information in SQLite. Primarily single-user (Randi), but supports additional contacts for notification routing and cross-platform identity resolution. Runs on `${CONTACTS_PORT}`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/contact` | Create a new contact |
| GET | `/contacts` | List all contacts |
| GET | `/contact/{contact_id}` | Get a specific contact by UUID |
| GET | `/search` | Search by alias (`?q=`) or field key/value (`?key=&value=`) |
| PUT | `/contact/{contact_id}` | Full replacement of a contact |
| PATCH | `/contact/{contact_id}` | Partial update (empty string deletes a field) |
| DELETE | `/contact/{contact_id}` | Delete a contact (cascades to aliases and fields) |

## Data Model

### Database Schema

```sql
contacts (id TEXT PK, notes TEXT)
aliases  (id INTEGER PK, contact_id FK, alias TEXT, UNIQUE(contact_id, alias))
fields   (id INTEGER PK, contact_id FK, key TEXT, value TEXT, UNIQUE(contact_id, key))
```

- Contact IDs are UUIDs
- Aliases are many-to-one (a contact can have multiple aliases)
- Fields are key-value pairs (imessage, discord, discord_id, email, or anything else)
- Foreign keys with `ON DELETE CASCADE`

### Pydantic Models (`shared/models/contacts.py`)

- **ContactCreate**: `aliases` (list), `fields` (list of dicts), `notes` (optional)
- **Contact** (response): `id`, `aliases`, `imessage`, `discord`, `discord_id`, `email`, `notes`
- **ContactUpdate**: All fields optional, for PATCH operations

### The `@ADMIN` Alias

**Critical**: The system depends on exactly one contact having the `@ADMIN` alias. Brain uses this to resolve the admin user for notifications and default routing. Uniqueness is enforced at the application level (`check_admin_alias_uniqueness()`), but there's no auto-creation or deletion protection.

## How Other Services Use Contacts

| Service | Usage |
|---------|-------|
| **Brain** | `get_admin_user_id()` searches for `@ADMIN`; `get_user_alias()` resolves user IDs to display names |
| **Brain notifications** | Fetches contact details to route messages to Discord/iMessage |
| **iMessage** | Searches by field key/value to resolve incoming sender handles to contact IDs |

### Search Behavior

- `GET /search?q=randi` — Searches aliases (case-insensitive via `COLLATE NOCASE`)
- `GET /search?key=discord_id&value=123456` — Searches fields (also case-insensitive)
- Returns **first match only**, not a list

## File Structure

```
app/
├── app.py              # FastAPI setup, middleware, startup
├── setup.py            # Database initialization (creates tables)
├── util.py             # get_db_connection(), @ADMIN uniqueness check
└── method/
    ├── post.py         # POST /contact
    ├── get.py          # GET /contacts, /contact/{id}, /search
    ├── put.py          # PUT /contact/{id}
    ├── patch.py        # PATCH /contact/{id}
    └── delete.py       # DELETE /contact/{id}
```

## Known Issues and Recommendations

### Issues

1. **Pydantic model mismatch** — Post/put handlers try to read top-level fields (`imessage`, `discord`, etc.) from `ContactCreate`, but those fields aren't defined on the input model. They only exist on the `Contact` response model. Clients must use the `fields` array instead; top-level field access silently fails via `getattr(..., None)`.

2. **No explicit transactions** — Multi-statement operations (insert contact → insert aliases → insert fields) aren't wrapped in transactions. A failure mid-operation can leave inconsistent state.

3. **Search returns single result** — `GET /search` returns only the first match with no indication that multiple contacts matched. Could be surprising with common field values.

4. **Case-insensitive search on all fields** — `COLLATE NOCASE` on field searches means `discord_id=ABC123` matches `abc123`. Fine for aliases, wrong for IDs.

5. **No pagination** — `GET /contacts` returns all contacts. Fine for current scale (<100), problematic at scale.

6. **Error messages leak SQLite details** — Database errors are returned directly to clients.

7. **@ADMIN is fragile** — No auto-creation, no deletion protection, no startup validation.

### Recommendations

- Add `imessage`, `discord`, `discord_id`, `email` as optional fields to `ContactCreate` and `ContactUpdate`
- Wrap compound operations in explicit transactions
- Consider returning a list from `/search` or at minimum documenting the single-result behavior
- Use case-sensitive matching for ID-type fields
- Add startup validation that `@ADMIN` exists (or auto-create it)
