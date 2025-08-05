#!/usr/bin/env python3

import asyncio
import httpx
import os
import json
from typing import Dict, Any

async def test_smarthome_mcp_via_http():
    """Test the smarthome MCP tool via HTTP requests to the brain service."""
    
    brain_port = os.getenv("BRAIN_PORT", "4207")
    base_url = f"http://localhost:{brain_port}"
    
    print("🏠 Testing Smarthome MCP Tool via HTTP")
    print("=" * 50)
    print(f"Brain service URL: {base_url}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Test 1: Check if brain service is running
        print("\n🏠 Test 1: Check brain service health")
        try:
            response = await client.get(f"{base_url}/ping")
            if response.status_code == 200:
                print("✅ Brain service is running")
            else:
                print(f"❌ Brain service returned status {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Cannot connect to brain service: {e}")
            print("Make sure Docker is running and brain service is started")
            return
        
        # Test 2: List available MCP tools
        print("\n🏠 Test 2: List available MCP tools")
        try:
            response = await client.get(f"{base_url}/mcp/tools")
            if response.status_code == 200:
                tools = response.json()
                tool_names = [tool.get("name") for tool in tools.get("tools", [])]
                print(f"✅ Available tools: {tool_names}")
                if "smarthome" in tool_names:
                    print("✅ Smarthome tool is registered")
                else:
                    print("❌ Smarthome tool is NOT registered")
                    return
            else:
                print(f"❌ Failed to get tools: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Error getting tools: {e}")
            return
        
        # Test 3: Missing user_request parameter
        print("\n🏠 Test 3: Missing user_request parameter")
        try:
            payload = {
                "tool_name": "smarthome",
                "parameters": {}
            }
            response = await client.post(f"{base_url}/mcp/execute", json=payload)
            result = response.json()
            print(f"Status: {response.status_code}")
            print(f"Success: {result.get('success', 'N/A')}")
            print(f"Error: {result.get('error', 'None')}")
            if not result.get('success') and 'required' in result.get('error', '').lower():
                print("✅ Correctly rejected missing parameter")
            else:
                print("❌ Should have rejected missing parameter")
        except Exception as e:
            print(f"❌ Error in test: {e}")
        
        # Test 4: Simple light control request
        print("\n🏠 Test 4: Simple light control request")
        try:
            payload = {
                "tool_name": "smarthome",
                "parameters": {
                    "user_request": "turn on the living room lights"
                }
            }
            response = await client.post(f"{base_url}/mcp/execute", json=payload)
            result = response.json()
            print(f"Status: {response.status_code}")
            print(f"Success: {result.get('success', 'N/A')}")
            print(f"Result keys: {list(result.get('result', {}).keys())}")
            
            if result.get('success'):
                res = result.get('result', {})
                print(f"Status: {res.get('status', 'N/A')}")
                print(f"Message: {res.get('message', 'N/A')}")
                if 'action_count' in res:
                    print(f"Actions executed: {res.get('action_count', 0)}")
                if 'action_summary' in res:
                    print("Action summaries:")
                    for summary in res.get('action_summary', [])[:3]:  # Show first 3
                        print(f"  - {summary}")
                print("✅ Request processed successfully")
            else:
                print(f"❌ Request failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error in test: {e}")
        
        # Test 5: Request with specific device
        print("\n🏠 Test 5: Request with specific device")
        try:
            payload = {
                "tool_name": "smarthome",
                "parameters": {
                    "user_request": "set brightness to 50%",
                    "device": "living room"
                }
            }
            response = await client.post(f"{base_url}/mcp/execute", json=payload)
            result = response.json()
            print(f"Status: {response.status_code}")
            print(f"Success: {result.get('success', 'N/A')}")
            
            if result.get('success'):
                res = result.get('result', {})
                print(f"Reasoning: {res.get('reasoning', 'N/A')[:100]}...")
                print("✅ Device-specific request processed")
            else:
                print(f"❌ Request failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error in test: {e}")
        
        # Test 6: Media recommendation request
        print("\n🏠 Test 6: Media recommendation request")
        try:
            payload = {
                "tool_name": "smarthome",
                "parameters": {
                    "user_request": "recommend something to watch"
                }
            }
            response = await client.post(f"{base_url}/mcp/execute", json=payload)
            result = response.json()
            print(f"Status: {response.status_code}")
            print(f"Success: {result.get('success', 'N/A')}")
            
            if result.get('success'):
                res = result.get('result', {})
                if 'intent' in res:
                    print(f"Intent: {res.get('intent', 'N/A')}")
                if 'recommendations' in res:
                    rec_count = len(res.get('recommendations', []))
                    print(f"Recommendations: {rec_count} items")
                print("✅ Media recommendation processed")
            else:
                print(f"❌ Request failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error in test: {e}")

if __name__ == "__main__":
    asyncio.run(test_smarthome_mcp_via_http())
