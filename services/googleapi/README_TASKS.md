# Google Tasks Integration

This module provides Google Tasks API integration for the Kirishima googleapi microservice, replacing the stickynotes service with enhanced functionality.

## Features

### Stickynotes (Default Task List)
- Create tasks with due dates and times
- RFC 5545 RRULE support for recurring tasks
- Automatic due date updates for recurring tasks on completion
- Due/overdue task monitoring with 60-second polling
- Integration with brain service for due task notifications

### Task Lists Management
- Create custom task lists
- Add/remove tasks from lists
- Delete task lists (except stickynotes)
- List all available task lists

### Monitoring
- Background monitor checks for due tasks every 60 seconds
- Tracks newly due tasks to avoid duplicate notifications
- Optional brain service notifications for newly due tasks
- Status endpoint for monitoring health

## API Endpoints

### Task Lists
- `POST /tasks/tasklists` - Create a new task list
- `GET /tasks/tasklists` - List all task lists (excluding stickynotes)
- `DELETE /tasks/tasklists/{id}` - Delete a task list
- `POST /tasks/tasklists/{id}/tasks` - Add task to specific list
- `DELETE /tasks/tasklists/{id}/tasks/{task_id}` - Remove task from list

### Stickynotes (Default Task List)
- `GET /tasks/stickynotes` - List all stickynotes tasks
- `POST /tasks/stickynotes` - Create a new stickynote task
- `PUT /tasks/stickynotes/{id}` - Update a stickynote task
- `POST /tasks/stickynotes/{id}/complete` - Complete task (handles recurrence)
- `DELETE /tasks/stickynotes/{id}` - Delete a stickynote task

### Due Tasks (Brain Service Integration)
- `GET /tasks/due` - Get current due and overdue tasks

### System
- `GET /tasks/validate` - Validate Google Tasks API access
- `GET /tasks/monitor/status` - Get monitor status

## Task Metadata

Tasks store Kirishima-specific metadata in the Google Tasks `notes` field:

```json
{
  "due_time": "14:30",
  "rrule": "FREQ=DAILY;INTERVAL=1",
  "kirishima": true
}
```

This metadata is parsed and exposed in API responses as separate fields.

## Recurring Tasks

Uses RFC 5545 RRULE format for recurrence patterns:

- **Daily**: `FREQ=DAILY;INTERVAL=1`
- **Weekly**: `FREQ=WEEKLY;INTERVAL=1`
- **Monthly**: `FREQ=MONTHLY;INTERVAL=1`
- **Custom**: Any valid RRULE string

When a recurring task is completed, its due date is automatically updated to the next occurrence instead of marking it complete.

## Configuration

Add to `config.json`:

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

## Google API Setup

1. Enable Google Tasks API in Google Cloud Console
2. Create OAuth2 credentials and download `credentials.json`
3. Place `credentials.json` in `/shared/credentials/`
4. First run will trigger OAuth flow to create `token.json`

Required OAuth scope: `https://www.googleapis.com/auth/tasks`

## Usage Examples

### Create a Recurring Task
```json
POST /tasks/stickynotes
{
  "title": "Take medication",
  "notes": "Daily reminder",
  "due": "2025-07-24",
  "due_time": "08:00",
  "rrule": "FREQ=DAILY;INTERVAL=1"
}
```

### Create a Shopping List
```json
POST /tasks/tasklists
{
  "title": "Grocery List"
}

POST /tasks/tasklists/{list_id}/tasks
{
  "title": "Milk"
}
```

### Get Due Tasks (Brain Service)
```json
GET /tasks/due
{
  "success": true,
  "due_tasks": [...],
  "overdue_tasks": [...]
}
```

## Migration from Stickynotes

This implementation replaces the stickynotes microservice with the following advantages:

1. **Cloud Storage**: Tasks stored in Google Tasks instead of local SQLite
2. **Cross-Platform**: Tasks sync across all Google Tasks clients
3. **Enhanced Metadata**: RFC 5545 RRULE support for complex recurrence
4. **Dual Purpose**: Both reminder tasks and general list management
5. **Better Integration**: Direct Google API access without custom database

## Monitoring

The monitor runs every 60 seconds and:
1. Fetches all incomplete tasks from the stickynotes list
2. Checks if any are due based on date and optional time
3. Tracks newly due tasks to avoid duplicate notifications
4. Optionally notifies the brain service of new due tasks

Monitor status available at `GET /tasks/monitor/status`.

## Error Handling

All endpoints return consistent error responses:
```json
{
  "success": false,
  "message": "Error description"
}
```

API authentication errors are logged and result in 500 responses. Invalid requests return 400 with validation details.
