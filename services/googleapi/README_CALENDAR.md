# Google Calendar Integration

This document provides additional details about the Google Calendar integration in the Kirishima googleapi service.

## Quick Start

1. **Enable Calendar API**: Make sure the Google Calendar API is enabled in your Google Cloud Console project
2. **Configure calendar ID**: Add the calendar configuration to `~/.kirishima/config.json`
3. **Start the service**: The calendar routes will be available at `/calendar/*`
4. **Enable monitoring**: Set `calendar.monitor.enabled: true` to monitor calendar changes

## Calendar ID Configuration

**Important**: The service is configured to ONLY operate on explicitly configured shared calendars. It will NOT fall back to your primary personal calendar to prevent accidental operations on the wrong calendar.

### From Shared Calendar URL

If someone shared a calendar with you via a URL like:

```text
https://calendar.google.com/calendar/u/0?cid=c2VrdGllQGdtYWlsLmNvbQ
```

The `cid` parameter (`c2VrdGllQGdtYWlsLmNvbQ`) is the base64-encoded calendar ID. Add it to your config:

```json
{
  "calendar": {
    "calendar_cid": "c2VrdGllQGdtYWlsLmNvbQ"
  }
}
```

The system will automatically decode this to get the actual calendar ID (in this case: `sektie@gmail.com`).

### Direct Calendar ID

If you know the calendar ID directly, you can specify it:

```json
{
  "calendar": {
    "calendar_id": "sektie@gmail.com"
  }
}
```

### Important Security Note

**All calendar operations (create, update, delete, search) will ONLY be performed on the explicitly configured shared calendar.** The service will:

- ✅ Validate calendar access on startup
- ✅ Reject operations if no calendar is configured
- ✅ Warn if you try to use your primary calendar (requires explicit override)
- ✅ Only create/modify events on the shared calendar

### Using Primary Calendar (Not Recommended)

If you really need to use your primary personal calendar, you must explicitly allow it:

```json
{
  "calendar": {
    "calendar_id": "primary",
    "allow_primary_calendar": true
  }
}
```

### Auto-Discovery

You can use the discovery endpoint to find available calendars:

```bash
curl http://localhost:4206/calendar/calendars/discover
```

This will show all calendars you have access to with their IDs and access levels.

## API Examples

### Create an Event

```bash
curl -X POST http://localhost:4206/calendar/events \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "Team Meeting",
    "description": "Weekly team sync",
    "location": "Conference Room A",
    "start_datetime": "2025-07-25T10:00:00-07:00",
    "end_datetime": "2025-07-25T11:00:00-07:00",
    "attendees": ["colleague@example.com"]
  }'
```

### Get Upcoming Events

```bash
curl http://localhost:4206/calendar/events/upcoming?max_results=5&days_ahead=7
```

### Check Current Calendar Configuration

```bash
curl http://localhost:4206/calendar/calendars/current
```

This will show you which calendar is currently configured and validate that it's accessible.

### Search Events

```bash
curl -X POST http://localhost:4206/calendar/events/search \
  -H "Content-Type: application/json" \
  -d '{
    "q": "meeting",
    "time_min": "2025-07-24T00:00:00Z",
    "time_max": "2025-07-31T23:59:59Z",
    "max_results": 10
  }'
```

## Monitoring Setup

### Polling Mode (Default)

This is the simplest setup that works without additional configuration:

```json
{
  "calendar": {
    "monitor": {
      "enabled": true,
      "poll_interval": 300,
      "brain_url": "http://brain:4207/api/multiturn"
    }
  }
}
```

### Push Notifications (Advanced)

For real-time notifications, you need a publicly accessible HTTPS endpoint:

```json
{
  "calendar": {
    "monitor": {
      "enabled": true,
      "push_notifications": {
        "enabled": true,
        "webhook_url": "https://yourdomain.com/api/googleapi/calendar/webhook/notifications",
        "expiration_hours": 24
      },
      "brain_url": "http://brain:4207/api/multiturn"
    }
  }
}
```

**Requirements for push notifications:**
- Valid SSL certificate (not self-signed)
- Publicly accessible URL
- URL must respond with 200 OK to Google's notifications

## Troubleshooting

### Common Issues

1. **"No calendar configured!"**
   - Add `calendar_cid` or `calendar_id` to your config.json
   - Use the discovery endpoint to find available calendar IDs
   - The service requires explicit calendar configuration for safety

2. **"Token file not found"**
   - Run the OAuth setup: `python scripts/google_oauth_setup.py`
   - Make sure the token.json file exists

3. **"Calendar not found or not accessible"**
   - Verify the calendar ID is correct
   - Check that you have read/write access to the calendar
   - Use the discovery endpoint to find available calendars
   - Make sure the calendar owner hasn't revoked your access

4. **"Using primary calendar is not allowed"**
   - This is a safety feature to prevent operations on your personal calendar
   - Configure a shared calendar using `calendar_cid` or `calendar_id`
   - If you really need to use your primary calendar, set `allow_primary_calendar: true`

5. **"Push notifications not working"**
   - Verify your webhook URL is publicly accessible
   - Check SSL certificate is valid
   - Monitor the service logs for webhook calls
   - Falls back to polling automatically

6. **"Permission denied"**
   - Make sure Calendar API is enabled in Google Cloud Console
   - Check OAuth scopes include calendar access
   - Re-run OAuth setup if needed

### Checking Service Status

```bash
# Check current calendar configuration and access
curl http://localhost:4206/calendar/calendars/current

# Check if calendar monitoring is active
curl http://localhost:4206/calendar/monitor/status

# Check all available calendars
curl http://localhost:4206/calendar/calendars

# Test basic functionality
curl http://localhost:4206/calendar/events/today
```

## Security Notes

- Calendar API uses the same OAuth2 tokens as Gmail
- Tokens are automatically refreshed when expired
- Service only accesses calendars you have explicit permission for
- Push notification webhooks should use HTTPS with valid certificates
- Consider limiting calendar access to specific calendars via Google Cloud Console API restrictions
