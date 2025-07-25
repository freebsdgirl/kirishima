#!/usr/bin/env python3
"""
Test script for Gmail NLP endpoint functionality
"""

import asyncio
import aiohttp
import json

async def test_gmail_nlp_endpoint():
    """Test the Gmail NLP endpoint with the new actions"""
    
    base_url = "http://localhost:4215"  # googleapi service port
    
    test_cases = [
        {
            "name": "Search Emails",
            "query": "search for emails from john about meeting",
            "expected_service": "gmail",
            "expected_action": "search_emails"
        },
        {
            "name": "Get Email by ID", 
            "query": "get email with ID abc123",
            "expected_service": "gmail",
            "expected_action": "get_email_by_id"
        },
        {
            "name": "Forward Email",
            "query": "forward email thread xyz789 to sarah with message please review this",
            "expected_service": "gmail",
            "expected_action": "forward_email"
        },
        {
            "name": "Send Email",
            "query": "send email to john about meeting tomorrow",
            "expected_service": "gmail", 
            "expected_action": "send_email"
        },
        {
            "name": "Get Upcoming Events",
            "query": "what meetings do I have coming up?",
            "expected_service": "calendar",
            "expected_action": "get_upcoming"
        }
    ]
    
    print("Testing Gmail NLP Endpoint")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. {test_case['name']}")
            print(f"Query: {test_case['query']}")
            print("-" * 50)
            
            try:
                payload = {"query": test_case["query"]}
                
                async with session.post(
                    f"{base_url}/nlp",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("success"):
                            action = result.get("action_taken", {})
                            print(f"✅ SUCCESS")
                            print(f"   Service: {action.get('service')}")
                            print(f"   Action: {action.get('action')}")
                            print(f"   Parameters: {json.dumps(action.get('parameters', {}), indent=6)}")
                            
                            # Check if it matches expected
                            if (action.get('service') == test_case['expected_service'] and 
                                action.get('action') == test_case['expected_action']):
                                print("✅ MATCHES EXPECTED")
                            else:
                                print(f"⚠️  Expected: {test_case['expected_service']}.{test_case['expected_action']}")
                                
                        else:
                            print(f"❌ FAILED: {result.get('error', 'Unknown error')}")
                            
                    else:
                        error_text = await response.text()
                        print(f"❌ HTTP {response.status}: {error_text}")
                        
            except aiohttp.ClientError as e:
                print(f"❌ CONNECTION ERROR: {e}")
            except Exception as e:
                print(f"❌ ERROR: {e}")
    
    print(f"\n{'='*60}")
    print("Gmail NLP endpoint testing complete!")

if __name__ == "__main__":
    asyncio.run(test_gmail_nlp_endpoint())
