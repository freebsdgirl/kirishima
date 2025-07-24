#!/usr/bin/env python3
"""
Test script for Google Contacts API implementation.

This script tests the basic functionality of the Google Contacts integration
in the googleapi microservice.
"""

import requests
import json
import sys

# Base URL for the googleapi service
BASE_URL = "http://localhost:4215"  # Adjust port if different

def test_cache_refresh():
    """Test refreshing the contacts cache."""
    print("Testing cache refresh...")
    try:
        response = requests.post(f"{BASE_URL}/contacts/cache/refresh")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Message: {data.get('message')}")
            print(f"Contacts refreshed: {data.get('contacts_refreshed')}")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    print()

def test_cache_status():
    """Test getting cache status."""
    print("Testing cache status...")
    try:
        response = requests.get(f"{BASE_URL}/contacts/cache/status")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Cache initialized: {data.get('cache_initialized')}")
            if 'stats' in data:
                stats = data['stats']
                print(f"Total contacts: {stats.get('total_contacts')}")
                print(f"Contacts with emails: {stats.get('contacts_with_emails')}")
                print(f"Last update: {stats.get('last_update')}")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    print()

def test_admin_contact():
    """Test getting the admin contact."""
    print("Testing admin contact retrieval...")
    try:
        response = requests.get(f"{BASE_URL}/contacts/admin")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Admin contact found:")
            if data.get('names'):
                print(f"  Name: {data['names'][0].get('display_name')}")
            if data.get('email_addresses'):
                for email in data['email_addresses']:
                    print(f"  Email: {email.get('value')} ({email.get('type', 'unknown')})")
        elif response.status_code == 404:
            print("Admin contact not found in cache")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    print()

def test_list_contacts():
    """Test listing all contacts."""
    print("Testing contacts list...")
    try:
        response = requests.get(f"{BASE_URL}/contacts/")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            contacts = data.get('contacts', [])
            print(f"Found {len(contacts)} contacts")
            print(f"Total items: {data.get('total_items')}")
            
            # Show first few contacts as sample
            for i, contact in enumerate(contacts[:3]):
                if contact.get('names'):
                    name = contact['names'][0].get('display_name', 'Unknown')
                    print(f"  {i+1}. {name}")
                    if contact.get('email_addresses'):
                        email = contact['email_addresses'][0].get('value')
                        print(f"     Email: {email}")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    print()

def test_contact_by_email():
    """Test getting a contact by email."""
    print("Testing contact by email (sektie@gmail.com)...")
    try:
        response = requests.get(f"{BASE_URL}/contacts/sektie@gmail.com")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Contact found:")
            if data.get('names'):
                print(f"  Name: {data['names'][0].get('display_name')}")
            if data.get('email_addresses'):
                for email in data['email_addresses']:
                    print(f"  Email: {email.get('value')} ({email.get('type', 'unknown')})")
        elif response.status_code == 404:
            print("Contact not found")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    print()

def main():
    """Run all tests."""
    print("Google Contacts API Test Script")
    print("=" * 40)
    
    # Test cache status first
    test_cache_status()
    
    # Refresh cache (this might take a while)
    test_cache_refresh()
    
    # Test cache status again
    test_cache_status()
    
    # Test admin contact
    test_admin_contact()
    
    # Test contact by email
    test_contact_by_email()
    
    # Test listing contacts
    test_list_contacts()
    
    print("Tests completed!")

if __name__ == "__main__":
    main()
