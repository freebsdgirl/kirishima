#!/usr/bin/env python3
"""
Test script for the new heatmap functionality.

This script tests the heatmap system by:
1. Sending sample weighted keywords to the update_heatmap endpoint
2. Checking the keyword scores
3. Getting top memories by heatmap score
"""

import asyncio
import httpx
import json

# Configuration
LEDGER_URL = "http://localhost:4203"

async def test_heatmap():
    """Test the heatmap functionality."""
    
    async with httpx.AsyncClient(timeout=60) as client:
        print("Testing heatmap functionality...")
        
        # Test 1: Update heatmap with sample keywords
        print("\n1. Testing heatmap update...")
        sample_keywords = {
            "programming": "high",
            "python": "high", 
            "database": "medium",
            "sqlite": "medium",
            "testing": "low",
            "debug": "low"
        }
        
        try:
            response = await client.post(
                f"{LEDGER_URL}/context/update_heatmap",
                json={"keywords": sample_keywords}
            )
            response.raise_for_status()
            result = response.json()
            print(f"✓ Heatmap update successful:")
            print(f"  New keywords: {result['new_keywords']}")
            print(f"  Updated keywords: {result['updated_keywords']}")
            print(f"  Affected memories: {result['affected_memories']}")
            
        except Exception as e:
            print(f"✗ Heatmap update failed: {e}")
            return
        
        # Test 2: Get keyword scores
        print("\n2. Testing keyword scores retrieval...")
        try:
            response = await client.get(f"{LEDGER_URL}/context/keyword_scores")
            response.raise_for_status()
            scores = response.json()["scores"]
            print(f"✓ Current keyword scores:")
            for keyword, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                print(f"  {keyword}: {score:.3f}")
                
        except Exception as e:
            print(f"✗ Keyword scores retrieval failed: {e}")
        
        # Test 3: Get top memories by heatmap
        print("\n3. Testing top memories retrieval...")
        try:
            response = await client.get(f"{LEDGER_URL}/context/top_memories?limit=5")
            response.raise_for_status()
            memories = response.json()["memories"]
            print(f"✓ Top {len(memories)} memories by heatmap score:")
            for memory in memories:
                print(f"  Score {memory['heatmap_score']:.3f}: {memory['memory'][:60]}...")
                
        except Exception as e:
            print(f"✗ Top memories retrieval failed: {e}")
        
        # Test 4: Update with different weights to test adjustment
        print("\n4. Testing keyword weight adjustment...")
        adjusted_keywords = {
            "programming": "low",  # Was high, should decrease
            "python": "high",      # Was high, should stay high
            "database": "high",    # Was medium, should increase
            "newtopic": "medium"   # New keyword
        }
        
        try:
            response = await client.post(
                f"{LEDGER_URL}/context/update_heatmap",
                json={"keywords": adjusted_keywords}
            )
            response.raise_for_status()
            result = response.json()
            print(f"✓ Weight adjustment successful:")
            print(f"  New keywords: {result['new_keywords']}")
            print(f"  Updated keywords: {result['updated_keywords']}")
            print(f"  Decayed keywords: {result['decayed_keywords']}")
            
            # Show updated scores
            response = await client.get(f"{LEDGER_URL}/context/keyword_scores")
            response.raise_for_status()
            scores = response.json()["scores"]
            print(f"  Updated scores:")
            for keyword, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                print(f"    {keyword}: {score:.3f}")
                
        except Exception as e:
            print(f"✗ Weight adjustment failed: {e}")

if __name__ == "__main__":
    print("Heatmap Test Script")
    print("==================")
    print("Make sure the ledger service is running on localhost:4203")
    print("This script will test the new heatmap functionality.")
    
    asyncio.run(test_heatmap())
