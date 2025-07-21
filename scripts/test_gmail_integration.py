#!/usr/bin/env python3
"""
Test script for Google API Gmail integration.

Usage:
    python scripts/test_gmail_integration.py

This script tests the Gmail integration by making requests to the GoogleAPI service endpoints.
"""
import httpx
import asyncio
import json

# Service URL (adjust if running outside Docker)
GOOGLEAPI_URL = "http://localhost:4215"  # Default GOOGLEAPI_PORT

async def test_gmail_endpoints():
    """Test various Gmail endpoints."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Testing Gmail Integration...")
        
        # Test service health
        print("\n1. Testing service health...")
        try:
            response = await client.get(f"{GOOGLEAPI_URL}/ping")
            if response.status_code == 200:
                print("✅ Service is healthy")
            else:
                print(f"❌ Service health check failed: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Cannot connect to service: {e}")
            return
        
        # Test get unread emails
        print("\n2. Testing unread emails...")
        try:
            response = await client.get(f"{GOOGLEAPI_URL}/gmail/unread?max_results=5")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {len(data.get('data', {}).get('emails', []))} unread emails")
            else:
                print(f"❌ Unread emails test failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Unread emails test error: {e}")
        
        # Test get recent emails
        print("\n3. Testing recent emails...")
        try:
            response = await client.get(f"{GOOGLEAPI_URL}/gmail/recent?max_results=5")
            if response.status_code == 200:
                data = response.json()
                emails = data.get('data', {}).get('emails', [])
                print(f"✅ Found {len(emails)} recent emails")
                if emails:
                    print(f"   Latest email from: {emails[0].get('from', 'Unknown')}")
                    print(f"   Subject: {emails[0].get('subject', 'No subject')}")
            else:
                print(f"❌ Recent emails test failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Recent emails test error: {e}")
        
        # Test email search
        print("\n4. Testing email search...")
        try:
            search_request = {
                "query": "is:unread",
                "max_results": 3
            }
            response = await client.post(f"{GOOGLEAPI_URL}/gmail/search", json=search_request)
            if response.status_code == 200:
                data = response.json()
                emails = data.get('data', {}).get('emails', [])
                print(f"✅ Search found {len(emails)} emails")
            else:
                print(f"❌ Email search test failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Email search test error: {e}")
        
        # Test monitoring status
        print("\n5. Testing monitoring status...")
        try:
            response = await client.get(f"{GOOGLEAPI_URL}/gmail/monitor/status")
            if response.status_code == 200:
                data = response.json()
                status = data.get('data', {}).get('status', {})
                print(f"✅ Monitor status: {'Running' if status.get('running') else 'Stopped'}")
                print(f"   Seen emails: {status.get('seen_emails_count', 0)}")
                print(f"   Poll interval: {status.get('poll_interval', 0)}s")
            else:
                print(f"❌ Monitor status test failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Monitor status test error: {e}")
        
        print("\n✅ Gmail integration testing completed!")

def main():
    """Run the test suite."""
    try:
        asyncio.run(test_gmail_endpoints())
    except KeyboardInterrupt:
        print("\n❌ Testing interrupted by user")
    except Exception as e:
        print(f"❌ Testing failed: {e}")

if __name__ == "__main__":
    main()
