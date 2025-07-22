#!/usr/bin/env python3
"""
Test the memory_search brainlet integration with the new heatmap system.
"""

import asyncio
import httpx
import json

# Configuration
BRAIN_URL = "http://localhost:4207"
LEDGER_URL = "http://localhost:4203"

async def test_memory_search_integration():
    """Test the complete memory search integration with heatmap."""
    
    print("Testing Memory Search + Heatmap Integration")
    print("==========================================")
    
    async with httpx.AsyncClient(timeout=60) as client:
        
        # Test 1: Simulate a conversation that should trigger memory search
        print("\n1. Testing memory search with conversation...")
        
        test_conversation = {
            "messages": [
                {
                    "role": "user", 
                    "content": "I'm working on a Python database project and need help with SQLite optimization"
                },
                {
                    "role": "assistant",
                    "content": "I can help you with SQLite optimization in Python. What specific issues are you encountering?"
                },
                {
                    "role": "user",
                    "content": "The queries are running slowly when I'm debugging my programming logic"
                }
            ]
        }
        
        try:
            # Send request to brain service to trigger memory search
            response = await client.post(
                f"{BRAIN_URL}/brainlets/memory_search",
                json=test_conversation
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"✓ Memory search completed successfully")
            if result.get('memory_search'):
                content = result.get('memory_search', [{}])[1].get('content', '')
                memory_count = len(content.split('\n')) if content else 0
                print(f"  Found memories: {memory_count}")
            else:
                print("  No memory_search result found")
            
        except Exception as e:
            print(f"✗ Memory search failed: {e}")
            return
        
        # Test 2: Check if heatmap was updated
        print("\n2. Checking if heatmap was updated...")
        
        try:
            response = await client.get(f"{LEDGER_URL}/context/keyword_scores")
            response.raise_for_status()
            scores = response.json()["scores"]
            
            print(f"✓ Heatmap contains {len(scores)} keywords:")
            for keyword, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {keyword}: {score:.3f}")
                
        except Exception as e:
            print(f"✗ Heatmap check failed: {e}")
        
        # Test 3: Check top memories by heatmap
        print("\n3. Checking top memories by current heatmap...")
        
        try:
            response = await client.get(f"{LEDGER_URL}/context/top_memories?limit=3")
            response.raise_for_status()
            memories = response.json()["memories"]
            
            print(f"✓ Top {len(memories)} memories by relevance:")
            for memory in memories:
                print(f"  Score {memory['heatmap_score']:.3f}: {memory['memory'][:80]}...")
                
        except Exception as e:
            print(f"✗ Top memories check failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_memory_search_integration())
