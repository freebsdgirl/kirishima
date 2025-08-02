#!/usr/bin/env python3
"""
Test script for the notification system.
"""

import requests
import json
import time

def test_notifications():
    """Test the notification endpoints."""
    
    base_url = "http://localhost:4206"
    
    print("Testing notification system...")
    
    # Test 1: Get notifications (should be empty initially)
    print("\n1. Getting notifications (should be empty)...")
    response = requests.get(f"{base_url}/notifications")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 2: Get notification stats
    print("\n2. Getting notification stats...")
    response = requests.get(f"{base_url}/notifications/stats")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 3: Simulate a calendar change notification
    print("\n3. Simulating calendar change notification...")
    test_notification = {
        'type': 'calendar_changes',
        'events_count': 2,
        'events': [
            {
                'id': 'test_event_1',
                'summary': 'Test Meeting',
                'start': {'dateTime': '2024-01-15T10:00:00Z'},
                'end': {'dateTime': '2024-01-15T11:00:00Z'}
            },
            {
                'id': 'test_event_2', 
                'summary': 'Another Meeting',
                'start': {'dateTime': '2024-01-15T14:00:00Z'},
                'end': {'dateTime': '2024-01-15T15:00:00Z'}
            }
        ],
        'timestamp': '2024-01-15T09:30:00Z',
        'source': 'googleapi_calendar_poll'
    }
    
    # We can't directly call the cache function from here, but we can test the endpoint
    # by manually inserting a notification into the database
    
    print("\n4. Testing notification retrieval with mark_processed=False...")
    response = requests.get(f"{base_url}/notifications?mark_processed=false")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    print("\n5. Testing notification retrieval with mark_processed=True...")
    response = requests.get(f"{base_url}/notifications?mark_processed=true")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    print("\n6. Getting final stats...")
    response = requests.get(f"{base_url}/notifications/stats")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    print("\nNotification system test completed!")

if __name__ == "__main__":
    test_notifications() 