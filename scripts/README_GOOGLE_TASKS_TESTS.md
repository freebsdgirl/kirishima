# Google Tasks Test Scripts

Two test scripts are provided to verify the Google Tasks API functionality:

## 1. Full Test Suite (`test_google_tasks.py`)

A comprehensive test suite with rich formatting and detailed output.

### Prerequisites
```bash
pip install httpx rich
```

### Usage
```bash
# Test against localhost:8000 (default)
python scripts/test_google_tasks.py

# Test against specific host/port
python scripts/test_google_tasks.py --host googleapi --port 8000

# Test with HTTPS
python scripts/test_google_tasks.py --host api.example.com --port 443 --https
```

### Features
- Rich console output with colors and tables
- Progress indicators during tests
- Detailed test results with formatted data
- Comprehensive cleanup

## 2. Simple Test Suite (`test_google_tasks_simple.py`)

A lightweight test suite using only Python standard library.

### Usage
```bash
# Test against localhost:8000 (default)
python scripts/test_google_tasks_simple.py

# Test against specific host/port
python scripts/test_google_tasks_simple.py googleapi 8000
```

### Features
- No external dependencies
- Basic but comprehensive testing
- Simple text output
- Suitable for CI/CD environments

## Tests Performed

Both scripts test the following functionality:

### 1. API Validation
- Validates Google Tasks API access
- Checks authentication and permissions

### 2. Monitor Status
- Tests the tasks monitor status endpoint
- Shows current monitoring configuration

### 3. Task Lists Management
- Creates a new test task list
- Lists all available task lists
- Adds tasks to the test list
- Deletes the test list (cleanup)

### 4. Stickynotes (Default Task List)
- Lists current stickynotes tasks
- Creates a simple task with due date
- Creates a task with specific due time
- Creates a recurring task with RRULE
- Updates a task
- Completes a recurring task (tests due date advancement)

### 5. Due Tasks (Brain Service Endpoint)
- Fetches current due and overdue tasks
- Displays summary of due tasks
- Shows sample due task data

### 6. Cleanup
- Removes all test tasks created
- Deletes test task list
- Leaves the system in original state

## Example Output

```
🚀 Google Tasks API Test Suite

Testing endpoint: http://localhost:8000

🔍 Testing API Validation
✅ API Validation
   Google Tasks access validated. Found 2 task lists.

📊 Testing Monitor Status
✅ Monitor Status
   ┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ Property              ┃ Value                 ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
   │ running               │ True                  │
   │ last_check            │ 2025-07-24T...        │
   │ seen_due_tasks_count  │ 0                     │
   │ poll_interval         │ 60                    │
   └───────────────────────┴───────────────────────┘

📋 Testing Task Lists
✅ List Task Lists
✅ Create Task List
   Created task list ID: MTIzNDU2...
✅ List Task Lists (after creation)

...

📊 Test Summary
✅ PASS API Validation
✅ PASS Monitor Status  
✅ PASS Task Lists
✅ PASS List Tasks
✅ PASS Stickynotes
✅ PASS Task Operations
✅ PASS Due Tasks

Total: 7/7 tests passed
🎉 All tests passed!
```

## Troubleshooting

### Authentication Errors
If you see authentication errors:
1. Ensure `credentials.json` is in `/shared/credentials/`
2. Check that Google Tasks API is enabled in Google Cloud Console
3. Verify OAuth2 credentials are valid
4. Run the OAuth flow by accessing any tasks endpoint first

### Connection Errors
If the script can't connect:
1. Verify the googleapi service is running
2. Check the host/port parameters
3. Ensure the service is accessible from your location

### Test Failures
If tests fail:
1. Check the googleapi service logs for errors
2. Verify Google Tasks API quotas haven't been exceeded
3. Ensure the service configuration is correct
4. Try running tests individually to isolate issues

## Running in Docker

If testing against a containerized service:
```bash
# From host machine, test containerized service
python scripts/test_google_tasks.py --host localhost --port 8000

# From within the docker network
python scripts/test_google_tasks.py --host googleapi --port 8000
```
