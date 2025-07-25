#!/usr/bin/env python3
"""
Simple test script for the NLP endpoint.

This script can be used to test the natural language processing endpoint
by sending sample queries and verifying the responses.
"""

import httpx
import json
import asyncio
from typing import Dict, Any

# Test configuration
GOOGLEAPI_BASE_URL = "http://localhost:4215"  # Adjust port as needed
NLP_ENDPOINT = f"{GOOGLEAPI_BASE_URL}/nlp"

# Sample test queries
TEST_QUERIES = [
    {
        "name": "Send Email Test",
        "query": "send sektie@gmail.com an email with subject 'Test Subject' and body 'This is a test email.'"
    },
    {
        "name": "Get Contact Test", 
        "query": "what is joanne newman's email address?"
    },
    {
        "name": "Create Calendar Event Test",
        "query": "add a meeting for tomorrow at 2 PM called 'Team Standup'"
    },
    {
        "name": "Search Emails Test",
        "query": "find emails from randi harper about ledger"
    },
    {
        "name": "Get Upcoming Events Test",
        "query": "what meetings do I have coming up?"
    }
]

async def test_nlp_endpoint(query: str) -> Dict[str, Any]:
    """
    Test the NLP endpoint with a given query.
    
    Args:
        query: Natural language query to test
        
    Returns:
        Dict containing the response from the endpoint
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                NLP_ENDPOINT,
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
                "success": False
            }
        except Exception as e:
            return {
                "error": f"Request failed: {str(e)}",
                "success": False
            }

async def run_tests():
    """Run all test queries and display results."""
    print("Testing NLP Endpoint")
    print("=" * 50)
    
    for i, test_case in enumerate(TEST_QUERIES, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"Query: {test_case['query']}")
        print("-" * 40)
        
        result = await test_nlp_endpoint(test_case['query'])
        
        if result.get('success'):
            print("✅ SUCCESS")
            action = result.get('action_taken', {})
            print(f"Service: {action.get('service', 'N/A')}")
            print(f"Action: {action.get('action', 'N/A')}")
            print(f"Parameters: {json.dumps(action.get('parameters', {}), indent=2)}")
        else:
            print("❌ FAILED")
            print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 50)
    print("Test completed")

if __name__ == "__main__":
    print("NLP Endpoint Test Script")
    print("Make sure the googleapi service is running on the expected port.")
    print("Press Ctrl+C to cancel, or Enter to continue...")
    
    try:
        input()
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
