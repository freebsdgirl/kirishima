# Discord Microservice

Bridges Discord DMs with the Kirishima system. Runs a Discord.py bot alongside a FastAPI server for outbound DM sending. DM-only — does not operate in servers. Runs on `${DISCORD_PORT}`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/dm` | Send a DM to a Discord user by user ID |
| GET | `/health` | Bot connection status (ready, logged in) |

## How It Works

### Incoming Messages (Discord → Brain)

```
Discord user sends DM
  → on_message event fires
  → look up contact by discord_id via contacts service (GET /search?key=discord_id&value={id})
  → build MultiTurnRequest (model="discord", platform="discord", user_id=contact.id)
  → POST to brain /api/multiturn
  → send brain's response back via ctx.send()
```

- Only processes DMs (ignores server messages, bot messages)
- Each message is sent as a single user message — brain/ledger handle conversation history
- Contact must already exist in the contacts service

### Outbound DMs (Brain → Discord)

Used by the notification system:

```
brain /notification/execute
  → POST /dm with {user_id: discord_user_id, content: "notification text"}
  → bot.fetch_user(user_id)
  → user.send(content)
```

Request model: `SendDMRequest(user_id: int, content: str)`

## File Structure

```
app/
├── app.py                      # FastAPI setup, bot startup
├── core/
│   ├── bot.py                  # BotManager: Discord bot config, lifecycle
│   └── events.py               # on_message, on_ready, on_error handlers
├── routes/
│   ├── dm.py                   # POST /dm endpoint
│   └── health.py               # GET /health endpoint
└── services/
    ├── message_handler.py      # Core: contact lookup → brain forwarding → reply
    ├── contacts.py             # Contact resolution + creation helpers
    └── dm.py                   # DM sending implementation
```

## Dependencies

- **Contacts service**: Resolves Discord user ID → Kirishima contact ID
- **Brain service**: Processes messages via `/api/multiturn`
- **Discord.py**: Bot framework for message events and DM sending

## Known Issues and Recommendations

### Issues

1. **HTTPException raised in Discord event handler** — `message_handler.py` raises FastAPI HTTPException inside `on_message`, which Discord.py doesn't understand. These exceptions are swallowed silently. Should catch and send a Discord error message instead.

2. **Registration command not implemented** — README previously claimed `register` command exists but no `@bot.command` decorators are defined anywhere. Contact creation methods exist in `contacts.py` but are never called.

3. **`awaiting_response` set is dead code** — `bot.py` initializes an `awaiting_response` set and `events.py` checks it, but nothing ever adds to or removes from the set. Feature is non-functional.

4. **Model hardcoded as "discord"** — `message_handler.py:89` sends `model="discord"` to brain. Unclear how proxy resolves this — should probably be a real mode name like `"default"`.

5. **Contact lookup failure blocks all processing** — If a Discord user has no contact record, message processing fails with no user-friendly feedback. Should auto-create or send a helpful error DM.

6. **Timeout inconsistency** — `message_handler.py` reads timeout from config.json, but `contacts.py` hardcodes 60s.

7. **No conversation history sent** — Each message sent as single-turn to brain. This works because brain/ledger handle history, but means the Discord service has no context for error recovery.

### Recommendations

- Replace HTTPException in event handlers with Discord message responses
- Either implement the registration command or remove references to it
- Remove dead `awaiting_response` code
- Fix model name to use a real mode
- Add graceful handling for unknown Discord users
