# Google Tasks Configuration

Add this to your `config.json` under the `googleapi` service configuration:

```json
{
  "tasks": {
    "monitor": {
      "enabled": true,
      "poll_interval": 60,
      "notify_brain": false,
      "brain_endpoint": "http://brain:8000/api/tasks/due"
    }
  }
}
```

## Configuration Options

- **`enabled`**: Whether to start tasks monitoring on service startup
- **`poll_interval`**: How often to check for due tasks (seconds, default: 60)
- **`notify_brain`**: Whether to automatically notify the brain service of newly due tasks
- **`brain_endpoint`**: Endpoint to notify when `notify_brain` is true

## Google API Setup

Ensure you have:
1. `credentials.json` - OAuth2 client credentials from Google Cloud Console
2. `token.json` - Will be created after first OAuth flow
3. Google Tasks API enabled in your Google Cloud project
4. Appropriate OAuth scopes configured

The Tasks API requires the scope:
- `https://www.googleapis.com/auth/tasks`
