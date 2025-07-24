# Google Calendar Integration

This document describes the Google Calendar integration for the Kirishima GoogleAPI service, which provides cached calendar access and management capabilities.

## Overview

The calendar integration provides:
- **Local caching** of calendar events in SQLite for fast queries
- **Background synchronization** with Google Calendar API
- **REST API endpoints** for calendar operations
- **Shared calendar enforcement** for security

## Architecture

```
Google Calendar API → Background Sync → SQLite Cache → REST Endpoints → Brain Service
```

The system uses a caching layer to minimize Google API calls and provide fast responses:

1. **Background Monitor**: Polls Google Calendar API every 5 minutes
2. **SQLite Cache**: Stores events locally for fast retrieval  
3. **REST API**: Serves cached data to other services
4. **Shared Calendar Only**: All operations restricted to configured shared calendar

## Configuration

### Database Configuration
```json
{
    "db": {
        "googleapi_calendar": "./shared/db/googleapi/calendar.db"
    }
}
```

### Calendar Configuration
```json
{
    "calendar": {
        "calendar_cid": "base64_encoded_calendar_id",
        "cache": {
            "enabled": true,
            "poll_interval": 300
        }
    }
}
```

**Configuration Options:**
- `calendar_cid`: Base64-encoded calendar ID from Google Calendar share URL
- `cache.enabled`: Enable/disable background caching (default: false)
- `cache.poll_interval`: Sync interval in seconds (default: 300)

### Calendar ID Setup

To get your `calendar_cid`:

1. Go to Google Calendar
2. Find your shared calendar
3. Click "Settings and sharing"
4. Copy the Calendar ID (email format)
5. Base64 encode it: `echo -n "your-calendar@gmail.com" | base64`
6. Use the result as `calendar_cid`

**Important**: The service is configured to ONLY operate on explicitly configured shared calendars. It will NOT fall back to your primary personal calendar to prevent accidental operations on the wrong calendar.

## Database Schema

The cache uses three main tables:

### `events` Table

- `id`: Google Calendar event ID (primary key)
- `calendar_id`: Calendar this event belongs to
- `summary`: Event title
- `description`: Event description
- `location`: Event location
- `start_datetime`/`end_datetime`: For timed events
- `start_date`/`end_date`: For all-day events
- `created`/`updated`: Google timestamps
- `status`: confirmed, tentative, cancelled
- `transparency`: opaque, transparent
- `visibility`: default, public, private
- `event_data`: Complete Google API response (JSON)
- `cached_at`: When this was cached locally

### `calendars` Table

- `id`: Calendar ID
- `summary`: Calendar name
- `description`: Calendar description
- `access_role`: User's access level
- `primary_calendar`: Boolean flag
- `cached_at`: Cache timestamp

### `cache_metadata` Table

- `key`: Metadata key (e.g., "last_sync")
- `value`: Metadata value
- `updated_at`: Last update time

## API Endpoints

### Calendar Information

- `GET /calendar/calendars/current` - Get current calendar info
- `GET /calendar/calendars/discover` - Discover available calendars
- `GET /calendar/calendars` - List accessible calendars

### Event Queries (Cached)

- `GET /calendar/events/upcoming?max_results=10&days_ahead=7` - Upcoming events
- `GET /calendar/events/today` - Today's events
- `GET /calendar/events/date-range?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Date range
- `POST /calendar/events/search` - Search events with criteria
- `GET /calendar/events/{event_id}` - Get specific event

### Event Management (Direct API)

- `POST /calendar/events` - Create new event
- `PUT /calendar/events/{event_id}` - Update event
- `DELETE /calendar/events/{event_id}` - Delete event

### Cache Management

- `GET /calendar/cache/stats` - Cache statistics
- `GET /calendar/monitor/status` - Cache status
- `POST /calendar/monitor/start` - Start caching
- `POST /calendar/monitor/stop` - Stop caching

## Request/Response Models

### CalendarEvent

```json
{
    "id": "event_id",
    "summary": "Event Title",
    "description": "Event description",
    "location": "Event location",
    "start": {
        "dateTime": "2025-07-24T10:00:00Z",
        "date": "2025-07-24"
    },
    "end": {
        "dateTime": "2025-07-24T11:00:00Z", 
        "date": "2025-07-24"
    },
    "created": "2025-07-20T08:00:00Z",
    "updated": "2025-07-20T08:00:00Z",
    "status": "confirmed"
}
```

### CreateEventRequest

```json
{
    "summary": "Event Title",
    "description": "Event description",
    "location": "Event location",
    "start_datetime": "2025-07-24T10:00:00Z",
    "end_datetime": "2025-07-24T11:00:00Z",
    "transparency": "opaque",
    "visibility": "default",
    "attendees": ["email@example.com"],
    "send_notifications": true
}
```

### SearchEventsRequest

```json
{
    "q": "search query",
    "time_min": "2025-07-24T00:00:00Z",
    "time_max": "2025-07-31T23:59:59Z",
    "max_results": 50,
    "order_by": "startTime"
}
```

## Security Features

### Shared Calendar Enforcement

- All operations restricted to configured shared calendar
- No access to primary calendar unless explicitly allowed
- Calendar ID validation on startup
- Base64 decoding with error handling

### Error Handling

- Invalid calendar IDs rejected
- Missing configuration handled gracefully
- Google API errors logged and surfaced
- Cache failures don't break service

## Background Synchronization

The cache sync process:

1. **Initialization**: Database tables created on first run
2. **Sync Window**: Gets events for next 90 days
3. **Full Refresh**: Replaces all cached events each sync
4. **Error Recovery**: Continues on API failures with exponential backoff
5. **Logging**: All sync operations logged for monitoring

## Performance Characteristics

### Query Performance

- **Cached queries**: ~1-5ms (SQLite local reads)
- **Direct API queries**: ~100-500ms (Google API calls)
- **Cache sync**: ~200-1000ms every 5 minutes (background)

### Storage Usage

- ~1KB per event on average
- ~90KB for 90 events (3 months)
- Automatic cleanup of old events

## Monitoring and Debugging

### Cache Statistics

```bash
curl http://localhost:4215/calendar/cache/stats
```

Returns:

```json
{
    "total_events": 45,
    "total_calendars": 1, 
    "last_sync": "2025-07-24T12:00:00Z",
    "database_path": "./shared/db/googleapi/calendar.db"
}
```

### Cache Status

```bash
curl http://localhost:4215/calendar/monitor/status
```

Returns:

```json
{
    "cache_enabled": true,
    "poll_interval": 300,
    "cache_active": true,
    "cache_stats": { /* stats object */ }
}
```

### Logs

Key log messages to monitor:

- `Calendar caching started successfully` - Startup OK
- `Calendar cache synced: N events cached` - Sync completed
- `Failed to sync calendar cache: error` - Sync problems
- `Calendar validation successful: summary` - Config valid

## Integration with Brain Service

The brain service can query calendar data using standard HTTP requests:

```python
import httpx

# Get upcoming events
response = httpx.get("http://googleapi:4215/calendar/events/upcoming")
events = response.json()

# Search for specific events
search_payload = {"q": "meeting", "max_results": 10}
response = httpx.post("http://googleapi:4215/calendar/events/search", json=search_payload)
results = response.json()
```

No automatic notifications are sent to brain - it queries on demand when users ask calendar-related questions.

## Troubleshooting

### Common Issues

**Cache not updating:**

- Check if `cache.enabled` is true
- Verify Google API credentials are valid
- Check logs for sync errors

**Calendar not found:**

- Verify `calendar_cid` is correct base64 encoding
- Ensure calendar is shared with service account
- Check calendar permissions

**Slow responses:**

- Cache may not be initialized - check startup logs
- Database may be locked - restart service
- SQLite file permissions issue

### Recovery Procedures

**Reset cache:**

```bash
# Stop service
docker-compose stop googleapi

# Remove cache database
rm ./shared/db/googleapi/calendar.db

# Restart service (will reinitialize)
docker-compose start googleapi
```

**Force sync:**

```bash
curl -X POST http://localhost:4215/calendar/monitor/stop
curl -X POST http://localhost:4215/calendar/monitor/start
```

## Development

### Adding New Endpoints

1. Add route to `app/routes/calendar.py`
2. Use `get_cached_events()` for queries
3. Use direct Google API for modifications
4. Update shared models in `shared/models/googleapi.py`

### Cache Schema Changes

1. Update `app/services/calendar/cache.py`
2. Add migration logic in `init_cache_db()`
3. Update models and serialization
4. Test with existing data

### Testing

Use the test script:

```bash
python scripts/test_calendar_integration.py
```

Tests:

- Calendar discovery and configuration
- Cached event queries
- Event creation/deletion
- Cache statistics
- Monitor status
