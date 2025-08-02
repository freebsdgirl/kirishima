# Google Calendar Integration

This service provides integration with Google Calendar API for event management and reminder notifications.

## Features

- **Event Management**: Create, update, delete, and search calendar events
- **Reminder Notifications**: Automatic notifications for upcoming events
- **Calendar Discovery**: Discover and manage shared calendars
- **Free/Busy Information**: Get availability information for time slots

## Configuration

Add the following configuration to your `config.json`:

```json
{
  "calendar": {
    "monitor": {
      "enabled": true,
      "poll_interval": 300,
      "notification_minutes": 30
    },
    "calendar_id": "primary"
  }
}
```

### Configuration Options

- **`enabled`**: Enable/disable calendar reminder monitoring (default: false)
- **`poll_interval`**: How often to check for upcoming events in seconds (default: 300 = 5 minutes)
- **`notification_minutes`**: How many minutes before an event to create a notification (default: 30)
- **`calendar_id`**: The calendar ID to monitor (default: "primary")

## Reminder System

The calendar service now uses a **reminder-based notification system** instead of change detection:

1. **Polling**: Checks for upcoming events every `poll_interval` seconds
2. **Time Window**: Looks for events starting within the next `notification_minutes` minutes
3. **Notification Creation**: Creates notifications for events that are approaching their start time
4. **Duplicate Prevention**: Prevents creating multiple notifications for the same event

### Notification Data Structure

Each reminder notification contains:

```json
{
  "type": "calendar_reminder",
  "event_id": "event_123",
  "summary": "Team Meeting",
  "start_time": "2024-01-15T10:00:00Z",
  "minutes_until_start": 25,
  "location": "Conference Room A",
  "description": "Weekly team sync",
  "html_link": "https://calendar.google.com/...",
  "timestamp": "2024-01-15T09:35:00Z",
  "source": "googleapi_calendar_reminder"
}
```

## API Endpoints

### Event Management
- `POST /calendar/events` - Create a new event
- `PUT /calendar/events/{event_id}` - Update an event
- `DELETE /calendar/events/{event_id}` - Delete an event
- `GET /calendar/events/{event_id}` - Get a specific event
- `GET /calendar/events/upcoming` - Get upcoming events
- `GET /calendar/events/today` - Get today's events
- `POST /calendar/events/search` - Search events
- `GET /calendar/events/date-range` - Get events in date range

### Calendar Management
- `GET /calendar/calendars` - List accessible calendars
- `GET /calendar/calendars/current` - Get current calendar info
- `GET /calendar/calendars/discover` - Discover shared calendars

### Monitoring
- `POST /calendar/monitor/start` - Start reminder monitoring
- `POST /calendar/monitor/stop` - Stop reminder monitoring
- `GET /calendar/monitor/status` - Get monitoring status

### Notifications
- `GET /calendar/notifications` - Get pending calendar notifications
- `GET /calendar/notifications/stats` - Get notification statistics

## Usage Examples

### Start Reminder Monitoring
```bash
curl -X POST http://localhost:8000/calendar/monitor/start
```

### Get Monitoring Status
```bash
curl http://localhost:8000/calendar/monitor/status
```

### Get Pending Notifications
```bash
curl http://localhost:8000/calendar/notifications
```

## Integration with Brain Service

The brain service can retrieve calendar reminders by calling:

```
GET /calendar/notifications
```

This endpoint returns pending reminder notifications and optionally marks them as processed. The brain service can then use this information to provide timely reminders to the user about upcoming calendar events.

## Monitoring Behavior

- **Polling Frequency**: Default 5 minutes (configurable)
- **Notification Window**: Default 30 minutes before event start (configurable)
- **Duplicate Prevention**: Won't create multiple notifications for the same event
- **Cancelled Events**: Automatically skips cancelled events
- **All-Day Events**: Handles both timed and all-day events
- **Error Handling**: Graceful error recovery with retry logic
