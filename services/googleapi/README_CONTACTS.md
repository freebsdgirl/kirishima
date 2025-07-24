# Google Contacts Integration

This document describes the Google Contacts integration added to the `googleapi` microservice.

## Overview

The Google Contacts integration provides access to Google Contacts via the People API, with local caching for performance. It's designed to replace the existing `contacts` microservice and provides a way to retrieve contact information, particularly the admin user contact.

## Configuration

Add the following configuration to your `config.json`:

```json
{
  "db": {
    "googleapi_contacts": "./shared/db/googleapi/contacts.db"
  },
  "contacts": {
    "admin_email": "sektie@gmail.com",
    "cache_on_startup": true
  }
}
```

### Configuration Options

- `db.googleapi_contacts`: Path to the SQLite database for caching contacts
- `contacts.admin_email`: Email address of the admin user to be returned by `/contacts/admin`
- `contacts.cache_on_startup`: Whether to refresh the contacts cache when the service starts

## API Endpoints

### GET /contacts/admin
Returns the admin contact configured in `config.json`.

**Response**: `GoogleContact` model

**Example**:
```bash
curl http://localhost:4206/contacts/admin
```

### GET /contacts/
Lists all contacts from the cache.

**Response**: `ContactsListResponse` model

**Example**:
```bash
curl http://localhost:4206/contacts/
```

### GET /contacts/{email}
Gets a specific contact by email address.

**Parameters**:
- `email`: The email address to search for

**Response**: `GoogleContact` model

**Example**:
```bash
curl http://localhost:4206/contacts/sektie@gmail.com
```

### POST /contacts/cache/refresh
Refreshes the contacts cache by fetching all contacts from Google API.

**Response**: `RefreshCacheResponse` model

**Example**:
```bash
curl -X POST http://localhost:4206/contacts/cache/refresh
```

### GET /contacts/cache/status
Gets the current status of the contacts cache.

**Response**: Cache status information

**Example**:
```bash
curl http://localhost:4206/contacts/cache/status
```

### POST /contacts/
Creates a new contact in Google Contacts.

**Request Body**: `CreateContactRequest` model

**Response**: `CreateContactResponse` model

**Example**:
```bash
curl -X POST http://localhost:4206/contacts/ \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "John Doe",
    "given_name": "John",
    "family_name": "Doe",
    "email_addresses": [
      {
        "value": "john@example.com",
        "type": "work"
      }
    ],
    "phone_numbers": [
      {
        "value": "+1234567890",
        "type": "mobile"
      }
    ],
    "notes": "Important contact"
  }'
```

## Data Models

### GoogleContact
```json
{
  "resource_name": "people/c12345",
  "etag": "abc123",
  "names": [
    {
      "display_name": "John Doe",
      "given_name": "John", 
      "family_name": "Doe"
    }
  ],
  "email_addresses": [
    {
      "value": "john@example.com",
      "type": "work"
    }
  ],
  "phone_numbers": [
    {
      "value": "+1234567890",
      "type": "mobile"
    }
  ]
}
```

### ContactsListResponse
```json
{
  "contacts": [...],
  "next_page_token": "abc123",
  "total_items": 150
}
```

### RefreshCacheResponse
```json
{
  "success": true,
  "message": "Cache refreshed successfully",
  "contacts_refreshed": 150,
  "timestamp": "2023-01-01T12:00:00Z"
}
```

### CreateContactRequest
```json
{
  "display_name": "John Doe",
  "given_name": "John",
  "family_name": "Doe",
  "middle_name": "Michael",
  "email_addresses": [
    {
      "value": "john@example.com",
      "type": "work"
    }
  ],
  "phone_numbers": [
    {
      "value": "+1234567890",
      "type": "mobile"
    }
  ],
  "addresses": [
    {
      "formatted_value": "123 Main St, Anytown, ST 12345",
      "street_address": "123 Main St",
      "city": "Anytown",
      "region": "ST",
      "postal_code": "12345",
      "country": "US",
      "type": "home"
    }
  ],
  "notes": "Important business contact"
}
```

### CreateContactResponse
```json
{
  "success": true,
  "message": "Contact created successfully",
  "contact": {
    "resource_name": "people/c12345",
    "names": [{"display_name": "John Doe"}]
  },
  "resource_name": "people/c12345"
}
```

## Authentication

The service uses the same OAuth2 credentials as the Gmail integration. Make sure you have:

1. Valid OAuth2 credentials in `/app/config/credentials.json`
2. Valid token in `/app/config/token.json`
3. The People API enabled for your Google Cloud project

## Caching

The service implements local SQLite caching to minimize API calls:

- **Database**: Stores contacts with names, emails, phones, addresses
- **Email Index**: Fast lookup by email address
- **Automatic Refresh**: Configurable cache refresh on startup
- **Manual Refresh**: Use `/cache/refresh` endpoint

### Database Schema

```sql
-- Main contacts table
CREATE TABLE contacts (
    resource_name TEXT PRIMARY KEY,
    etag TEXT,
    display_name TEXT,
    given_name TEXT,
    family_name TEXT,
    middle_name TEXT,
    raw_data TEXT,  -- JSON storage for complete contact data
    cached_at TEXT,
    modified_at TEXT
);

-- Email lookup table
CREATE TABLE contact_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_name TEXT,
    email TEXT,
    email_type TEXT,
    is_primary BOOLEAN DEFAULT 0,
    FOREIGN KEY (resource_name) REFERENCES contacts (resource_name)
);
```

## Testing

Use the provided test script to verify the integration:

```bash
python /home/randi/kirishima/scripts/test_google_contacts.py
```

This script tests:

- Cache refresh functionality
- Cache status retrieval
- Admin contact lookup
- Contact search by email
- Contact creation via API
- Contact listing

## Error Handling

The service returns appropriate HTTP status codes:

- `200`: Success
- `404`: Contact not found
- `500`: Server error (API issues, database problems, etc.)

All errors are logged with detailed information for debugging.

## Service Integration

This Google Contacts integration is designed to replace the existing `contacts` microservice. The key difference is that it pulls contact data from Google Contacts instead of maintaining a local database of contacts.

The `/contacts/admin` endpoint specifically returns the contact for the email address configured in `contacts.admin_email`, making it easy to retrieve the admin user's contact information from the centralized Google Contacts.
