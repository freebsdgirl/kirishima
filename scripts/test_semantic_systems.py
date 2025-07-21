#!/usr/bin/env python3
"""
Test script for semantic memory and scanning systems.

This script tests the new semantic endpoints to ensure they're working correctly.
"""

import asyncio
import httpx
import json

# Configuration
LEDGER_HOST = "localhost"
LEDGER_PORT = 4203
BASE_URL = f"http://{LEDGER_HOST}:{LEDGER_PORT}"

async def test_semantic_scan_preview():
    """Test the semantic scan preview endpoint"""
    print("🧪 Testing semantic scan preview...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/memories/_scan_semantic/preview",
                params={
                    "similarity_threshold": 0.7,
                    "min_cluster_size": 3,
                    "max_clusters_to_process": 5
                }
            )
            
            if response.status_code == 503:
                print("❌ Sentence-transformers not available - this is expected if not installed")
                return False
            
            response.raise_for_status()
            data = response.json()
            
            print("✅ Semantic scan preview endpoint working")
            print(f"   Total messages: {data.get('total_messages', 0)}")
            print(f"   Clusters found: {data.get('total_clusters_found', 0)}")
            print(f"   Would process: {data.get('clusters_would_process', 0)}")
            
            return True
            
        except httpx.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

async def test_semantic_dedup_preview():
    """Test the semantic deduplication preview endpoint"""
    print("🧪 Testing semantic deduplication preview...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/memories/_dedup_semantic/preview",
                params={
                    "similarity_threshold": 0.8,
                    "max_clusters_to_process": 5
                }
            )
            
            if response.status_code == 503:
                print("❌ Sentence-transformers not available - this is expected if not installed")
                return False
            
            response.raise_for_status()
            data = response.json()
            
            print("✅ Semantic deduplication preview endpoint working")
            print(f"   Total memories: {data.get('total_memories', 0)}")
            print(f"   Clusters found: {data.get('clusters_found', 0)}")
            print(f"   Would process: {data.get('clusters_would_process', 0)}")
            
            return True
            
        except httpx.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

async def test_endpoints():
    """Test all semantic endpoints"""
    print("🚀 Testing semantic memory systems endpoints\n")
    
    # Test semantic scan preview
    scan_ok = await test_semantic_scan_preview()
    print()
    
    # Test semantic deduplication preview
    dedup_ok = await test_semantic_dedup_preview()
    print()
    
    if scan_ok and dedup_ok:
        print("✅ All semantic endpoints are working correctly!")
        return True
    elif not scan_ok and not dedup_ok:
        print("ℹ️  Semantic systems require sentence-transformers to be installed")
        print("   Install with: pip install sentence-transformers scikit-learn")
        return False
    else:
        print("⚠️  Some endpoints working, some not - check installation")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_endpoints())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)
