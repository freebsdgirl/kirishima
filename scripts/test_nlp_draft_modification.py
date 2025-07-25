#!/usr/bin/env python3
"""
Simple test to verify the NLP service saves drafts instead of sending emails.
This test is for verification purposes and assumes the googleapi service is running.
"""

import asyncio
import httpx
import json

async def test_email_to_draft():
    """Test that 'send email' action actually saves a draft."""
    
    # Sample natural language query for sending an email
    query = "send an email to john@example.com with subject 'Test Email' and body 'This is a test message'"
    
    # First, test the NLP parsing
    async with httpx.AsyncClient() as client:
        try:
            # Parse the natural language query
            response = await client.post(
                "http://localhost:4206/api/nlp/parse",
                json={"query": query}
            )
            
            if response.status_code == 200:
                parsed_action = response.json()
                print(f"✅ Query parsed successfully:")
                print(f"   Service: {parsed_action.get('service')}")
                print(f"   Action: {parsed_action.get('action')}")
                print(f"   Parameters: {parsed_action.get('parameters')}")
                
                # Execute the action
                execute_response = await client.post(
                    "http://localhost:4206/api/nlp/execute",
                    json=parsed_action
                )
                
                if execute_response.status_code == 200:
                    result = execute_response.json()
                    print(f"\n✅ Action executed successfully:")
                    print(f"   Message: {result.get('message')}")
                    print(f"   Success: {result.get('success')}")
                    print(f"   Email ID: {result.get('email_id')}")
                    print(f"   Status: {result.get('status')}")
                    if '_debug_note' in result:
                        print(f"   Debug: {result.get('_debug_note')}")
                    
                    # Check if it looks like it was sent but actually saved as draft
                    if (result.get('message') == "Email sent successfully" and 
                        result.get('status') == "sent" and 
                        result.get('_debug_note') == "Actually saved as draft"):
                        print(f"\n🎉 SUCCESS: Email appears to be sent but was actually saved as draft!")
                    else:
                        print(f"\n⚠️  UNEXPECTED: Response doesn't match expected draft behavior")
                        
                else:
                    print(f"❌ Failed to execute action: {execute_response.status_code} - {execute_response.text}")
                    
            else:
                print(f"❌ Failed to parse query: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Error during test: {e}")
            print("Note: Make sure the googleapi service is running on port 4206")

if __name__ == "__main__":
    print("Testing NLP email-to-draft modification...")
    print("This test requires the googleapi service to be running.\n")
    asyncio.run(test_email_to_draft())
