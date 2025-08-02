#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the path to import from the project
sys.path.append('/home/randi/kirishima/services/brain/app')

from services.mcp.lists import lists

async def test_lists_tool():
    """Test the lists MCP tool with the new terminology."""
    
    print("🧪 Testing Lists Tool")
    print("=" * 50)
    
    # Test 1: List all lists
    print("\n📋 Test 1: List all lists")
    result = await lists({"action": "list_lists"})
    print(f"Success: {result.success}")
    print(f"Result: {result.result}")
    if result.error:
        print(f"Error: {result.error}")
    
    # Test 2: Create a test list
    print("\n📋 Test 2: Create a test list")
    result = await lists({"action": "create_list", "title": "Test List for Lists Tool"})
    print(f"Success: {result.success}")
    print(f"Result: {result.result}")
    if result.error:
        print(f"Error: {result.error}")
    
    list_id = result.result.get("list_id") if result.success else None
    
    if list_id:
        # Test 3: Add an item to the list
        print("\n📋 Test 3: Add an item to the list")
        result = await lists({"action": "add_item", "list_id": list_id, "title": "Test Item 1"})
        print(f"Success: {result.success}")
        print(f"Result: {result.result}")
        if result.error:
            print(f"Error: {result.error}")
        
        item_id = result.result.get("item_id") if result.success else None
        
        # Test 4: List items in the list
        print("\n📋 Test 4: List items in the list")
        result = await lists({"action": "list_items", "list_id": list_id})
        print(f"Success: {result.success}")
        print(f"Result: {result.result}")
        if result.error:
            print(f"Error: {result.error}")
        
        if item_id:
            # Test 5: Remove the item
            print("\n📋 Test 5: Remove the item")
            result = await lists({"action": "remove_item", "list_id": list_id, "item_id": item_id})
            print(f"Success: {result.success}")
            print(f"Result: {result.result}")
            if result.error:
                print(f"Error: {result.error}")
        
        # Test 6: Delete the test list
        print("\n📋 Test 6: Delete the test list")
        result = await lists({"action": "delete_list", "list_id": list_id})
        print(f"Success: {result.success}")
        print(f"Result: {result.result}")
        if result.error:
            print(f"Error: {result.error}")
    
    print("\n✅ Lists tool testing complete!")

if __name__ == "__main__":
    asyncio.run(test_lists_tool())
