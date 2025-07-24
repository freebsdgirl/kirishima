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

### Calendar Integration

- **Create events**: Create new calendar events with attendees, reminders
- **Update events**: Modify existing calendar events
- **Delete events**: Remove calendar events
- **Search events**: Search events by text, date range, and other criteria
- **Get upcoming events**: Retrieve upcoming events from the calendar
- **Get today's events**: Retrieve events for the current day
- **Calendar discovery**: Find shared calendars the user has access to
- **Free/busy information**: Get availability information for scheduling
- **Automatic monitoring**: Monitor calendar changes and forward them to the brain service
- **Push notifications**: Support for real-time calendar change notifications (webhook-based)
- **Polling fallback**: Automatic fallback to polling mode if push notifications fail

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
  },
  "calendar": {
    "calendar_cid": "c2VrdGllQGdtYWlsLmNvbQ",
    "monitor": {
      "enabled": true,
      "poll_interval": 300,
      "brain_url": "http://brain:4207/api/multiturn",
      "push_notifications": {
        "enabled": false,
        "webhook_url": "https://yourdomain.com/api/googleapi/calendar/webhook/notifications", 
        "expiration_hours": 24
      }
    }
  }
}
```

#### Calendar Configuration Options:

- **calendar_cid**: Base64-encoded calendar ID from a shared calendar URL (e.g., `https://calendar.google.com/calendar/u/0?cid=c2VrdGllQGdtYWlsLmNvbQ`)
- **calendar_id**: Direct calendar ID (alternative to calendar_cid)
- **monitor.enabled**: Enable/disable calendar change monitoring
- **monitor.poll_interval**: Polling interval in seconds (fallback mode)
- **monitor.brain_url**: URL to forward calendar changes to the brain service
- **monitor.push_notifications.enabled**: Enable push notifications (requires webhook setup)
- **monitor.push_notifications.webhook_url**: Public HTTPS URL for receiving calendar notifications
- **monitor.push_notifications.expiration_hours**: Hours before notification channel expires

### 4. Finding Your Calendar ID

If you have a shared calendar, you can find the calendar ID in several ways:

1. **From the share URL**: The `cid` parameter is the base64-encoded calendar ID
   - URL: `https://calendar.google.com/calendar/u/0?cid=c2VrdGllQGdtYWlsLmNvbQ`
   - Decode `c2VrdGllQGdtYWlsLmNvbQ` to get `sektie@gmail.com`

2. **Use the discovery endpoint**:
   ```bash
   GET /calendar/calendars/discover
   ```

3. **List all calendars**:
   ```bash
   GET /calendar/calendars
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

### Calendar API Endpoints

#### Create Event

```bash
POST /calendar/events
{
  "summary": "Team Meeting",
  "description": "Weekly team sync meeting",
  "location": "Conference Room A",
  "start_datetime": "2025-07-24T10:00:00-07:00",
  "end_datetime": "2025-07-24T11:00:00-07:00",
  "attendees": ["john@example.com", "jane@example.com"],
  "send_notifications": true
}
```

#### Update Event

```bash
PUT /calendar/events/{event_id}
{
  "summary": "Updated Team Meeting",
  "location": "Conference Room B",
  "start_datetime": "2025-07-24T14:00:00-07:00",
  "end_datetime": "2025-07-24T15:00:00-07:00"
}
```

#### Get Event

```bash
GET /calendar/events/{event_id}
```

#### Delete Event

```bash
DELETE /calendar/events/{event_id}?send_notifications=true
```

#### Get Upcoming Events

```bash
GET /calendar/events/upcoming?max_results=10&days_ahead=7
```

#### Get Today's Events

```bash
GET /calendar/events/today
```

#### Search Events

```bash
POST /calendar/events/search
{
  "q": "meeting",
  "time_min": "2025-07-24T00:00:00Z",
  "time_max": "2025-07-31T23:59:59Z",
  "max_results": 20
}
```

#### Get Events by Date Range

```bash
GET /calendar/events/date-range?start_date=2025-07-24T00:00:00Z&end_date=2025-07-31T23:59:59Z&max_results=100
```

#### List Calendars

```bash
GET /calendar/calendars
```

#### Discover Shared Calendars

```bash
GET /calendar/calendars/discover
```

#### Get Free/Busy Information

```bash
POST /calendar/freebusy
{
  "time_min": "2025-07-24T00:00:00Z",
  "time_max": "2025-07-24T23:59:59Z",
  "calendars": ["primary", "sektie@gmail.com"]
}
```

#### Calendar Monitoring Control

```bash
POST /calendar/monitor/start    # Start monitoring
POST /calendar/monitor/stop     # Stop monitoring
GET /calendar/monitor/status    # Get monitoring status
```

#### Push Notification Webhook

```bash
POST /calendar/webhook/notifications  # Handle Google's push notifications
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

## Calendar Monitoring

The service can automatically monitor Google Calendar for changes and forward them to the brain service. This enables the AI assistant to:

- Notify about upcoming events
- Respond to calendar changes
- Provide scheduling assistance
- Maintain awareness of the user's schedule

### Monitoring Modes

1. **Push Notifications (Preferred)**: Real-time notifications via Google's webhook system
   - Requires a publicly accessible HTTPS endpoint
   - More efficient and responsive
   - Automatic fallback to polling if setup fails

2. **Polling (Fallback)**: Regular checks for calendar changes
   - Uses incremental sync for efficiency
   - Works without webhook setup
   - Configurable polling interval (default: 5 minutes)

### How Push Notifications Work

1. Service registers a webhook URL with Google Calendar API
2. Google sends POST requests to the webhook when calendar changes occur
3. Service processes the notification and forwards changes to brain service
4. Notification channels expire after 24 hours and are automatically renewed

### How Polling Works

1. Service polls Calendar API every 5 minutes (configurable)
2. Uses sync tokens for incremental changes only
3. Forwards detected changes to brain service
4. Maintains sync state across restarts

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
