# Google Calendar Integration

This service provides integration with Google Calendar API for event management.

## Features

- **Event Management**: Create, update, delete, and search calendar events
- **Calendar Discovery**: Discover and manage shared calendars
- **Free/Busy Information**: Get availability information for time slots
- **Simple Queries**: Get upcoming events, today's events, this week's events, and next event

## Configuration

Add the following configuration to your `config.json`:

```json
{
  "calendar": {
    "calendar_cid": "base64_encoded_calendar_id_from_share_url"
  }
}
```

### Configuration Options

- **`calendar_cid`**: Base64-encoded calendar ID from Google Calendar share URL (for shared calendars)
- **`calendar_id`**: Direct calendar ID (alternative to calendar_cid)

## API Endpoints

### Event Management
- `POST /calendar/events` - Create a new event
- `PUT /calendar/events/{event_id}` - Update an event
- `DELETE /calendar/events/{event_id}` - Delete an event
- `GET /calendar/events/{event_id}` - Get a specific event
- `GET /calendar/events/upcoming` - Get upcoming events
- `GET /calendar/events/next-event` - Get the next upcoming event
- `GET /calendar/events/today` - Get today's events
- `GET /calendar/events/this-week` - Get events for this week
- `POST /calendar/events/search` - Search events
- `GET /calendar/events/date-range` - Get events in date range

### Calendar Management
- `GET /calendar/calendars` - List accessible calendars
- `GET /calendar/calendars/current` - Get current calendar info
- `GET /calendar/calendars/discover` - Discover shared calendars

### Free/Busy
- `POST /calendar/freebusy` - Get free/busy information

## Usage Examples

### Get Next Event
```bash
curl http://localhost:8000/calendar/events/next-event
```

### Get Today's Events
```bash
curl http://localhost:8000/calendar/events/today
```

### Get This Week's Events
```bash
curl http://localhost:8000/calendar/events/this-week
```

### Create an Event
```bash
curl -X POST http://localhost:8000/calendar/events \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "Team Meeting",
    "description": "Weekly team sync",
    "start_datetime": "2024-01-15T10:00:00-07:00",
    "end_datetime": "2024-01-15T11:00:00-07:00"
  }'
```

### Search Events
```bash
curl -X POST http://localhost:8000/calendar/events/search \
  -H "Content-Type: application/json" \
  -d '{
    "q": "meeting",
    "time_min": "2024-01-15T00:00:00Z",
    "time_max": "2024-01-22T23:59:59Z"
  }'
```

## Integration Notes

- **No Caching**: This service directly queries the Google Calendar API for all operations
- **No Monitoring**: Calendar monitoring has been removed in favor of a future courier service
- **Shared Calendars**: Supports shared calendars via calendar_cid configuration
- **Error Handling**: All endpoints include proper error handling and logging

## Future Plans

- Calendar notifications will be handled by a dedicated courier service
- Push notifications will be implemented through the courier service
- Real-time event updates will be managed by the courier service
