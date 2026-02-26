# iMessage Microservice

Bridges iMessage with the Kirishima system via BlueBubbles (running on an iMac). Receives webhook events for incoming messages, forwards them to brain, and sends replies back through BlueBubbles. Runs on `${IMESSAGE_PORT}`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/imessage/send` | Send an iMessage to a phone number/address |
| POST | `/imessage/recv` | Receive incoming iMessage webhook from BlueBubbles |

## How It Works

### Incoming Messages (iMessage → Brain)

```
BlueBubbles webhook fires (new-message, isFromMe=false)
  → POST /imessage/recv
  → extract sender address, text, timestamp, chat GUID
  → look up contact via contacts service (GET /search?key=imessage&value={address})
  → build MultiTurnRequest (model="imessage", platform="imessage", user_id=contact.id)
  → POST to brain /api/multiturn
  → extract response text
  → send reply via BlueBubblesClient.send_message(sender_address, reply)
```

Only processes `type == "new-message"` and `isFromMe == false` payloads. Everything else is ignored.

### Outbound Messages (Brain → iMessage)

Used by the notification system:

```
brain /notification/execute
  → POST /imessage/send with {address: "+15555555555", message: "notification text"}
  → BlueBubblesClient.send_message(address, message)
  → if chat doesn't exist, creates via create_chat_and_send()
```

Request model: `OutgoingiMessage(address: str, message: str)`

### BlueBubbles Client

- Authenticates via `password` query parameter on all requests
- Uses `POST /api/v1/message/text` for sending to existing chats
- Uses `POST /api/v1/chat/new` for creating chats (auto-triggered on 500 "Chat does not exist")
- Chat GUID format: `iMessage;+;{address}`

## Configuration

From `config.json` and environment variables:

```json
{
    "bluebubbles": {
        "host": "localhost",
        "port": 3000,
        "password": "bluebubbles"
    }
}
```

Environment overrides: `BLUEBUBBLES_HOST`, `BLUEBUBBLES_PORT`, `BLUEBUBBLES_PASSWORD`

## File Structure

```
app/
├── app.py                      # FastAPI setup, BlueBubbles client init
├── routes/
│   └── imessage.py             # /send and /recv endpoints
└── services/
    ├── client.py               # BlueBubblesClient: HTTP wrapper for BB API
    ├── send.py                 # send_message() with auto chat creation
    └── recv.py                 # Webhook processing: parse → contact lookup → brain → reply
```

## Dependencies

- **BlueBubbles**: iMessage bridge running on macOS (separate infrastructure)
- **Contacts service**: Resolves sender address → Kirishima contact ID
- **Brain service**: Processes messages via `/api/multiturn`

## Known Issues and Recommendations

### Issues

1. **Error handling in `/recv` breaks webhook pipeline** — Contact lookup failure raises HTTPException (500), which means BlueBubbles doesn't get a 200 acknowledgment and may retry, causing duplicate processing. Should return 200 and log the error.

2. **No empty text validation** — If `data.get("text")` is None or empty, it's forwarded to brain as-is. Should filter before processing.

3. **`ProxyiMessageRequest` is dead code** — Defined in `shared/models/imessage.py` but never imported or used anywhere. Old model predating the MultiTurnRequest approach.

4. **Model hardcoded as "imessage"** — `recv.py` sends `model="imessage"` to brain. Like Discord, should probably be a real mode name.

5. **Brain response format assumed** — `reply_payload.get("response", {})` assumes specific brain response structure with no validation. Silent failure if format changes.

6. **BlueBubbles password in query params** — Visible in logs and potentially proxied firewalls. Should use HTTP header if BlueBubbles supports it.

7. **Invalid timestamps silently replaced** — If `dateCreated` is invalid, falls back to `datetime.now()` without logging. Could skew message ordering in ledger.

### Recommendations

- Return 200 from `/recv` even on internal errors (acknowledge webhook, log failure)
- Add text validation before forwarding to brain
- Remove unused `ProxyiMessageRequest` model
- Add specific timeout exception handling (separate from generic errors)
- Log warnings for timestamp fallbacks
