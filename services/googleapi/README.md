# Google API Service

This service provides integration with Google APIs (Gmail, Calendar, Tasks, People) for the Kirishima AI assistant system.

## Features

### Gmail Integration

- **Send emails**: Send new emails with attachments, CC/BCC support
- **Reply to emails**: Reply to email threads
- **Search emails**: Full-text search using Gmail query syntax
- **Retrieve emails**: Get specific emails by ID, unread emails, recent emails
- **Search by criteria**: Find emails by sender, subject, etc.
- **Automatic monitoring**: Monitor inbox for new emails and forward them to the brain service

### Authentication

- OAuth2 flow for secure Google API access
- Automatic token refresh
- Configurable token and credentials paths

## Setup

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Gmail API
   - Google Calendar API
   - Google Tasks API
   - People API
   - Contacts API

4. Create OAuth2 credentials:
   - Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
   - Application type: "Desktop application"
   - Download the JSON file as `credentials.json`

### 2. OAuth2 Token Setup

1. Copy `credentials.json` to `~/.kirishima/credentials.json`
2. Run the OAuth setup script:

   ```bash
   cd /home/randi/kirishima
   python scripts/google_oauth_setup.py
   ```

3. Follow the browser OAuth flow to authorize the application
4. The script will save `token.json` to `~/.kirishima/token.json`

### 3. Configuration

Configure the service in `~/.kirishima/config.json`:

```json
{
  "gmail": {
    "token_path": "/root/.kirishima/token.json",
    "credentials_path": "/root/.kirishima/credentials.json",
    "monitor": {
      "enabled": true,
      "poll_interval": 30,
      "brain_url": "http://brain:8000"
    }
  }
}
```

## Usage

### Start the Service

```bash
docker-compose up googleapi
```

The service will automatically start email monitoring if enabled in the configuration.

### API Endpoints

#### Send Email

```bash
POST /gmail/send
{
  "to": "recipient@example.com",
  "subject": "Hello",
  "body": "Email content",
  "cc": "cc@example.com",
  "bcc": "bcc@example.com"
}
```

#### Reply to Email

```bash
POST /gmail/reply
{
  "thread_id": "thread_id_here",
  "body": "Reply content"
}
```

#### Search Emails

```bash
POST /gmail/search
{
  "query": "from:sender@example.com subject:important",
  "max_results": 10
}
```

#### Get Unread Emails

```bash
GET /gmail/unread?max_results=10
```

#### Get Recent Emails

```bash
GET /gmail/recent?max_results=10
```

#### Get Specific Email

```bash
GET /gmail/email/{email_id}
```

#### Search by Sender

```bash
POST /gmail/search/sender
{
  "value": "sender@example.com",
  "max_results": 10
}
```

#### Search by Subject

```bash
POST /gmail/search/subject
{
  "value": "meeting",
  "max_results": 10
}
```

#### Monitoring Control

```bash
POST /gmail/monitor/start    # Start monitoring
POST /gmail/monitor/stop     # Stop monitoring
GET /gmail/monitor/status    # Get monitoring status
```

## Email Monitoring

The service can automatically monitor the Gmail inbox for new emails and forward them to the brain service as MultiTurnRequest objects. This enables the AI assistant to:

- Respond to incoming emails
- Process email content for context
- Take actions based on email content
- Maintain conversation history across email threads

### How it Works

1. Polls Gmail API every 30 seconds (configurable)
2. Detects new unread emails
3. Extracts email content and metadata
4. Creates MultiTurnRequest with sender as user ID
5. Forwards to brain service at `/api/multiturn`
6. Brain service processes the email and can respond via the assistant

### Configuration Options

- `enabled`: Enable/disable automatic monitoring
- `poll_interval`: Seconds between Gmail API polls (default: 30)
- `brain_url`: URL of the brain service

## Error Handling

- OAuth2 tokens are automatically refreshed when expired
- Failed API calls are logged with detailed error messages
- Monitoring continues running even if individual emails fail to process
- All endpoints return standardized error responses with appropriate HTTP status codes

## Security

- OAuth2 tokens are stored securely in JSON format
- Credentials and tokens are mounted from the host filesystem
- No hardcoded API keys or sensitive data in the codebase
- Scoped access to only required Google APIs

## Dependencies

- `google-api-python-client`: Google API client library
- `google-auth`: Google authentication library
- `google-auth-oauthlib`: OAuth2 flow support
- `httpx`: Async HTTP client for brain service communication
- `fastapi`: Web framework for REST API
- `uvicorn`: ASGI server
