# Natural Language Processing (NLP) Endpoint

This document describes the `/nlp` endpoint that allows users to interact with Google services using natural language queries.

## Overview

The `/nlp` endpoint accepts natural language requests and converts them into structured Google API actions using an LLM. It supports Gmail, Calendar, and Contacts operations.

## Endpoint

**POST** `/nlp`

### Request Format

```json
{
  "query": "natural language query"
}
```

### Response Format

```json
{
  "success": true,
  "action_taken": {
    "service": "gmail|calendar|contacts",
    "action": "action_name",
    "parameters": {
      "key": "value"
    }
  },
  "result": {
    "result_data": "..."
  },
  "error": null
}
```

## Supported Actions

### Gmail Service

#### Send Email
- **Natural Language**: "send joanne newman an email with the text: Randi says she'll eat dinner with you tonight."
- **Action**: `send_email`
- **Contact Resolution**: If you provide a name instead of an email address, the system will look up the contact's email address automatically
- **Parameters**: `to`, `subject`, `body`, `cc` (optional), `bcc` (optional)

#### Search Emails
- **Natural Language**: "find emails from john about the meeting"
- **Action**: `search_emails`
- **Parameters**: `query` (Gmail search syntax)

#### Get Unread Emails
- **Natural Language**: "show me my unread emails"
- **Action**: `get_unread`
- **Parameters**: None

### Calendar Service

#### Create Event
- **Natural Language**: "add a new appointment for october 4th at 7:30 AM with the title 'Doctor Appointment'"
- **Action**: `create_event`
- **Parameters**: `summary`, `start_datetime`, `end_datetime`, `description` (optional), `location` (optional), `attendees` (optional)
- **Date/Time Format**: ISO 8601 format (YYYY-MM-DDTHH:MM:SS-TZ:00)

#### Search Events
- **Natural Language**: "find meetings with john next week"
- **Action**: `search_events`
- **Parameters**: `query`, `start_date` (optional), `end_date` (optional)

#### Get Upcoming Events
- **Natural Language**: "what meetings do I have coming up?"
- **Action**: `get_upcoming`
- **Parameters**: `max_results` (optional, default 10)

### Contacts Service

#### Get Contact
- **Natural Language**: "what is joanne newman's email address?"
- **Action**: `get_contact`
- **Parameters**: `email` (can be email address or contact name)

#### List Contacts
- **Natural Language**: "show me all my contacts"
- **Action**: `list_contacts`
- **Parameters**: None

## Examples

### Send Email Example

**Request:**
```json
{
  "query": "send john.doe@example.com an email with subject 'Meeting Tomorrow' and body 'Don't forget about our meeting at 2 PM tomorrow.'"
}
```

**Response:**
```json
{
  "success": true,
  "action_taken": {
    "service": "gmail",
    "action": "send_email",
    "parameters": {
      "to": "john.doe@example.com",
      "subject": "Meeting Tomorrow",
      "body": "Don't forget about our meeting at 2 PM tomorrow."
    }
  },
  "result": {
    "email_id": "abc123",
    "message": "Email sent successfully",
    "resolved_to": "john.doe@example.com"
  }
}
```

### Create Calendar Event Example

**Request:**
```json
{
  "query": "schedule a team meeting for next Monday at 10 AM for 1 hour"
}
```

**Response:**
```json
{
  "success": true,
  "action_taken": {
    "service": "calendar",
    "action": "create_event",
    "parameters": {
      "summary": "Team Meeting",
      "start_datetime": "2025-07-28T10:00:00-07:00",
      "end_datetime": "2025-07-28T11:00:00-07:00"
    }
  },
  "result": {
    "event_id": "def456",
    "message": "Event created successfully",
    "event_details": {
      "event_id": "def456",
      "summary": "Team Meeting",
      "start_datetime": "2025-07-28T10:00:00-07:00",
      "end_datetime": "2025-07-28T11:00:00-07:00"
    }
  }
}
```

### Get Contact Example

**Request:**
```json
{
  "query": "what is sarah's email address?"
}
```

**Response:**
```json
{
  "success": true,
  "action_taken": {
    "service": "contacts",
    "action": "get_contact",
    "parameters": {
      "email": "sarah"
    }
  },
  "result": {
    "contact": {
      "resource_name": "people/c789",
      "names": [
        {
          "display_name": "Sarah Johnson",
          "given_name": "Sarah",
          "family_name": "Johnson"
        }
      ],
      "email_addresses": [
        {
          "value": "sarah.johnson@example.com",
          "type": "work"
        }
      ]
    },
    "message": "Contact found"
  }
}
```

## Error Handling

If an error occurs, the response will have `success: false` and include an error message:

```json
{
  "success": false,
  "action_taken": null,
  "result": null,
  "error": "Could not find email address for contact: unknown person"
}
```

## Technical Implementation

1. **LLM Integration**: The endpoint uses the proxy service's `/api/singleturn` endpoint with model='email' to parse natural language queries
2. **Contact Resolution**: For email operations, contact names are automatically resolved to email addresses using the contacts service
3. **Action Mapping**: The LLM response is mapped to existing Google API endpoints
4. **Error Handling**: Comprehensive error handling for parsing failures, service unavailability, and action execution errors

## Configuration

The endpoint uses the existing Google API service configuration and requires:
- Proper Google API authentication (OAuth2)
- Access to the proxy service for LLM communication
- The prompt template at `/app/config/prompts/googleapi/nlp_action_parser.j2`
