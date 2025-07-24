#!/usr/bin/env python3
"""
Test script for Google Calendar integration.
This script tests the basic functionality of the calendar service via HTTP endpoints.

Usage:
    python scripts/test_calendar_integration.py

Prerequisites:
    1. GoogleAPI service must be running on localhost:4206
    2. OAuth2 credentials must be configured (run google_oauth_setup.py)
    3. Calendar must be configured in ~/.kirishima/config.json

The script will test:
    - Calendar discovery and current configuration
    - Getting upcoming events and today's events
    - Searching events
    - Creating and deleting test events
    - Monitor status checking
"""

import requests
import json
import sys
import os
from datetime import datetime, timedelta, timezone

# Calendar service base URL
BASE_URL = "http://localhost:4215/calendar"

def test_calendar_discovery():
    """Test calendar discovery functionality."""
    print("Testing calendar discovery...")
    
    try:
        # Test current calendar configuration
        response = requests.get(f"{BASE_URL}/calendars/current")
        if response.status_code == 200:
            data = response.json()
            calendar_info = data.get('data', {})
            print(f"Current calendar: {calendar_info.get('summary')} (ID: {calendar_info.get('calendar_id')})")
            print(f"Access role: {calendar_info.get('access_role')}")
            print(f"Primary: {calendar_info.get('primary')}")
        else:
            print(f"Current calendar check failed: {response.status_code} - {response.text}")
        
        # Test discovering all calendars
        response = requests.get(f"{BASE_URL}/calendars/discover")
        if response.status_code == 200:
            data = response.json()
            calendars = data.get('data', {}).get('calendars', [])
            print(f"Discovered {len(calendars)} calendars:")
            
            for calendar in calendars[:3]:  # Show first 3
                print(f"  - {calendar.get('summary')} (ID: {calendar.get('id')}, "
                      f"Access: {calendar.get('accessRole')}, Primary: {calendar.get('primary', False)})")
            
            return True
        else:
            print(f"Calendar discovery failed: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"Calendar discovery test failed: {e}")
        return False


def test_upcoming_events():
    """Test getting upcoming events."""
    print("\nTesting upcoming events...")
    
    try:
        response = requests.get(f"{BASE_URL}/events/upcoming?max_results=5&days_ahead=7")
        
        if response.status_code == 200:
            events = response.json()
            print(f"Found {len(events)} upcoming events:")
            
            for event in events:
                summary = event.get('summary', 'No title')
                start = event.get('start', {})
                start_time = start.get('dateTime', start.get('date', 'No time'))
                print(f"  - {summary} at {start_time}")
            
            return True
        else:
            print(f"Get upcoming events failed: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"Upcoming events test failed: {e}")
        return False


def test_create_test_event():
    """Test creating a simple test event."""
    print("\nTesting event creation...")
    
    try:
        # Create a test event for tomorrow
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        event_data = {
            "summary": "Test Event from Kirishima",
            "description": "This is a test event created by the Kirishima calendar integration",
            "start_datetime": start_time.isoformat(),
            "end_datetime": end_time.isoformat(),
            "send_notifications": False
        }
        
        response = requests.post(
            f"{BASE_URL}/events",
            headers={"Content-Type": "application/json"},
            json=event_data
        )
        
        if response.status_code == 200:
            result = response.json()
            event_data = result.get('data', {})
            event_id = event_data.get('event_id')
            print(f"Created test event: {event_data.get('summary')} (ID: {event_id})")
            return event_id
        else:
            print(f"Event creation failed: {response.status_code} - {response.text}")
            return None
        
    except Exception as e:
        print(f"Event creation test failed: {e}")
        return None


def test_delete_test_event(event_id):
    """Test deleting the test event."""
    if not event_id:
        print("\nSkipping event deletion (no event ID)")
        return
    
    print(f"\nTesting event deletion for {event_id}...")
    
    try:
        response = requests.delete(f"{BASE_URL}/events/{event_id}?send_notifications=false")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("Successfully deleted test event")
            else:
                print(f"Failed to delete test event: {result.get('message')}")
        else:
            print(f"Event deletion failed: {response.status_code} - {response.text}")
        
    except Exception as e:
        print(f"Event deletion test failed: {e}")


def test_monitor_setup():
    """Test monitor setup (without actually starting monitoring)."""
    print("\nTesting monitoring setup...")
    
    try:
        response = requests.get(f"{BASE_URL}/monitor/status")
        
        if response.status_code == 200:
            result = response.json()
            status = result.get('data', {})
            print(f"Monitor status: {status}")
            return True
        else:
            print(f"Monitor status check failed: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"Monitor setup test failed: {e}")
        return False


def test_today_events():
    """Test getting today's events."""
    print("\nTesting today's events...")
    
    try:
        response = requests.get(f"{BASE_URL}/events/today")
        
        if response.status_code == 200:
            events = response.json()
            print(f"Found {len(events)} events today:")
            
            for event in events:
                summary = event.get('summary', 'No title')
                start = event.get('start', {})
                start_time = start.get('dateTime', start.get('date', 'No time'))
                print(f"  - {summary} at {start_time}")
            
            return True
        else:
            print(f"Get today's events failed: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"Today's events test failed: {e}")
        return False


def test_search_events():
    """Test searching events."""
    print("\nTesting event search...")
    
    try:
        # Search for events with "test" in the title
        search_data = {
            "q": "test",
            "max_results": 5
        }
        
        response = requests.post(
            f"{BASE_URL}/events/search",
            headers={"Content-Type": "application/json"},
            json=search_data
        )
        
        if response.status_code == 200:
            result = response.json()
            events = result.get('events', [])
            print(f"Found {len(events)} events matching 'test':")
            
            for event in events:
                summary = event.get('summary', 'No title')
                start = event.get('start', {})
                start_time = start.get('dateTime', start.get('date', 'No time'))
                print(f"  - {summary} at {start_time}")
            
            return True
        else:
            print(f"Event search failed: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"Event search test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=== Google Calendar Integration Test ===\n")
    
    # Check if service is running
    try:
        response = requests.get(f"{BASE_URL}/calendars/current", timeout=5)
        if response.status_code not in [200, 500]:  # 500 is ok if calendar not configured yet
            print(f"ERROR: Calendar service not responding. Status: {response.status_code}")
            print("Make sure the GoogleAPI service is running on localhost:4206")
            return 1
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Cannot connect to calendar service: {e}")
        print("Make sure the GoogleAPI service is running on localhost:4206")
        return 1
    
    test_results = []
    
    # Test calendar discovery and configuration
    test_results.append(test_calendar_discovery())
    
    # Test upcoming events
    test_results.append(test_upcoming_events())
    
    # Test today's events
    test_results.append(test_today_events())
    
    # Test event search
    test_results.append(test_search_events())
    
    # Test event creation and deletion
    event_id = test_create_test_event()
    if event_id:
        test_results.append(True)
        test_delete_test_event(event_id)
    else:
        test_results.append(False)
    
    # Test monitor setup
    test_results.append(test_monitor_setup())
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed! Calendar integration is working correctly.")
        return 0
    else:
        print("Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
