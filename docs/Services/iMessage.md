# 💬 iMessage

## Purpose

This service acts as an adapter between Kirishima and the BlueBubbles API for iMessage communication. It handles both outgoing message delivery and incoming webhook forwarding to Brain.

## Port

4204

## Endpoints

### `GET /ping`

Health check for the iMessage microservice.

```json
{ "status": "ok" }
```

### `POST /imessage/send`

Send an iMessage via the BlueBubbles server.

**Request Body:** `OutgoingMessage`

```json
{
  "address": "+15555555555",
  "message": "Hey, are you free?"
}
```

**Response:**

```json
{
  "status": "sent",
  "response": {
    // Full response from BlueBubbles
  }
}
```

- Uses `send_message()` on the internal BlueBubbles client
- If the target chat doesn’t exist, falls back to `create_chat_and_send()`

### `POST /imessage/recv`

Webhook endpoint for incoming messages from the BlueBubbles server.

**Behavior:**

- Filters only `"type": "new-message"` payloads
- Ignores messages authored by self (`isFromMe: true`)
- Extracts sender info, chat ID, text, and timestamp
- Transforms payload into standardized `IncomingMessage` format
- Forwards it to Brain at `/message/incoming` using `BRAIN_INCOMING_URL`
- If Brain responds with a message (under `reply.reply`), the service replies via BlueBubbles

**Example Transformed Payload Sent to Brain:**

```json
{
  "platform": "imessage",
  "sender_id": "+15555555555",
  "text": "Don’t forget your meds",
  "timestamp": "2025-04-09T04:00:00Z",
  "metadata": {
    "chat_id": "iMessage;+;+15555555555"
  }
}
```

### `GET /docs/export`

Exposes OpenAPI route metadata for contract inspection. Used to support centralized service documentation.

## Classes

### `OutgoingMessage` (Pydantic Model)

Represents an outgoing iMessage with recipient address and text content.

### `BlueBubblesClient`

Internal client used to send messages via BlueBubbles API.

- `send_message(address, message)` attempts direct send
- If the target chat is missing, falls back to `create_chat_and_send`
- Uses config variables:
  - `BLUEBUBBLES_SERVER`
  - `BLUEBUBBLES_PORT`
  - `BLUEBUBBLES_PASSWORD`

## Configuration

Stored in `imessage.config`:

```python
BLUEBUBBLES_SERVER = "10.0.1.10"
BLUEBUBBLES_PORT = 12346
BLUEBUBBLES_PASSWORD = "*******"
BRAIN_INCOMING_URL = "http://localhost:4207/message/incoming"
```

- All outbound replies and webhook forwarding use this configuration.
- No authentication headers—this service assumes local-only deployment.

## Logging & Monitoring

This service logs:

- All incoming webhook payloads (debug)
- Self-authored or irrelevant messages (debug)
- Message delivery attempts and failures
- All forwarded payloads and Brain’s responses

Logs are routed to Graylog via the system-wide logger.
