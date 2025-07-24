#!/usr/bin/env python3
"""
Simple Google Tasks API Test Script

A lightweight test script for Google Tasks functionality that only uses standard library.
Useful for basic testing without additional dependencies.

Usage:
    python test_google_tasks_simple.py [HOST] [PORT]

Examples:
    python test_google_tasks_simple.py
    python test_google_tasks_simple.py localhost 8000
    python test_google_tasks_simple.py googleapi 8000
"""

import json
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class SimpleTasksTestClient:
    """Simple test client using only standard library."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.test_task_list_id: Optional[str] = None
        self.test_task_ids: list = []
    
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request using urllib."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Prepare request
            req_data = None
            headers = {'Content-Type': 'application/json'}
            
            if data:
                req_data = json.dumps(data).encode('utf-8')
            
            req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            
            # Make request
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                
                try:
                    json_data = json.loads(response_data)
                except json.JSONDecodeError:
                    json_data = {"text": response_data}
                
                return {
                    "status_code": response.status,
                    "success": True,
                    "data": json_data
                }
                
        except urllib.error.HTTPError as e:
            try:
                error_data = json.loads(e.read().decode('utf-8'))
            except:
                error_data = {"error": f"HTTP {e.code}"}
            
            return {
                "status_code": e.code,
                "success": False,
                "data": error_data
            }
        except Exception as e:
            return {
                "status_code": 0,
                "success": False,
                "error": str(e)
            }
    
    def print_result(self, test_name: str, result: Dict[str, Any]):
        """Print test result."""
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{status} {test_name}")
        
        if not result["success"]:
            if "error" in result:
                print(f"   Error: {result['error']}")
            elif "data" in result and isinstance(result["data"], dict):
                if "message" in result["data"]:
                    print(f"   Message: {result['data']['message']}")
        elif "data" in result and isinstance(result["data"], dict):
            if "message" in result["data"]:
                print(f"   {result['data']['message']}")
    
    def test_validation(self):
        """Test API validation."""
        print("\n🔍 Testing API Validation")
        result = self.make_request("GET", "/tasks/validate")
        self.print_result("API Validation", result)
        return result["success"]
    
    def test_monitor_status(self):
        """Test monitor status."""
        print("\n📊 Testing Monitor Status")
        result = self.make_request("GET", "/tasks/monitor/status")
        self.print_result("Monitor Status", result)
        
        if result["success"] and isinstance(result["data"], dict):
            print("   Monitor Status:")
            for key, value in result["data"].items():
                print(f"     {key}: {value}")
        
        return result["success"]
    
    def test_task_lists(self):
        """Test task list operations."""
        print("\n📋 Testing Task Lists")
        
        # List existing task lists
        result = self.make_request("GET", "/tasks/tasklists")
        self.print_result("List Task Lists", result)
        
        # Create test task list
        test_list_name = f"Test List {datetime.now().strftime('%H:%M:%S')}"
        result = self.make_request("POST", "/tasks/tasklists", {
            "title": test_list_name
        })
        self.print_result("Create Task List", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            self.test_task_list_id = data.get("task_list_id")
            print(f"   Created task list ID: {self.test_task_list_id}")
        
        return result["success"]
    
    def test_list_tasks(self):
        """Test adding tasks to lists."""
        if not self.test_task_list_id:
            print("\n⚠️  Skipping list tasks test - no test list available")
            return True
        
        print("\n📝 Testing List Tasks")
        
        # Add some tasks to the test list
        test_tasks = [
            {"title": "Buy milk"},
            {"title": "Buy bread"},
            {"title": "Buy eggs", "notes": "Organic preferred"}
        ]
        
        success = True
        for task_data in test_tasks:
            result = self.make_request(
                "POST", 
                f"/tasks/tasklists/{self.test_task_list_id}/tasks",
                task_data
            )
            self.print_result(f"Add '{task_data['title']}' to list", result)
            success = success and result["success"]
        
        return success
    
    def test_stickynotes(self):
        """Test stickynotes functionality."""
        print("\n🗒️  Testing Stickynotes")
        
        # List current stickynotes
        result = self.make_request("GET", "/tasks/stickynotes")
        self.print_result("List Stickynotes", result)
        
        # Create simple task
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        simple_task = {
            "title": "Test simple task",
            "notes": "This is a test task",
            "due": tomorrow
        }
        
        result = self.make_request("POST", "/tasks/stickynotes", simple_task)
        self.print_result("Create Simple Task", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            task_id = data.get("task_id")
            if task_id:
                self.test_task_ids.append(task_id)
        
        # Create task with due time
        timed_task = {
            "title": "Test timed task",
            "notes": "Task with specific time",
            "due": tomorrow,
            "due_time": "14:30"
        }
        
        result = self.make_request("POST", "/tasks/stickynotes", timed_task)
        self.print_result("Create Timed Task", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            task_id = data.get("task_id")
            if task_id:
                self.test_task_ids.append(task_id)
        
        # Create recurring task
        today = datetime.now().strftime('%Y-%m-%d')
        recurring_task = {
            "title": "Test daily recurring task",
            "notes": "This task repeats daily",
            "due": today,
            "due_time": "09:00", 
            "rrule": "FREQ=DAILY;INTERVAL=1"
        }
        
        result = self.make_request("POST", "/tasks/stickynotes", recurring_task)
        self.print_result("Create Recurring Task", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            task_id = data.get("task_id")
            if task_id:
                self.test_task_ids.append(task_id)
        
        return len(self.test_task_ids) > 0
    
    def test_task_operations(self):
        """Test task update and completion."""
        if not self.test_task_ids:
            print("\n⚠️  Skipping task operations test - no test tasks available")
            return True
        
        print("\n⚙️  Testing Task Operations")
        
        task_id = self.test_task_ids[0]
        
        # Update task
        update_data = {
            "title": "Updated test task",
            "notes": "This task has been updated"
        }
        
        result = self.make_request("PUT", f"/tasks/stickynotes/{task_id}", update_data)
        self.print_result("Update Task", result)
        
        # Complete recurring task if available
        if len(self.test_task_ids) > 2:
            result = self.make_request("POST", f"/tasks/stickynotes/{self.test_task_ids[2]}/complete")
            self.print_result("Complete Recurring Task", result)
            
            if result["success"] and "data" in result and result["data"]:
                data = result["data"]["data"] if "data" in result["data"] else result["data"]
                if data and data.get("recurring"):
                    print(f"   Next due date: {data.get('next_due')}")
        
        return result["success"]
    
    def test_due_tasks(self):
        """Test due tasks endpoint."""
        print("\n⏰ Testing Due Tasks")
        
        result = self.make_request("GET", "/tasks/due")
        self.print_result("Get Due Tasks", result)
        
        if result["success"] and "data" in result:
            data = result["data"]
            due_count = len(data.get("due_tasks", []))
            overdue_count = len(data.get("overdue_tasks", []))
            
            print(f"   Due tasks: {due_count}")
            print(f"   Overdue tasks: {overdue_count}")
            
            # Show first few due tasks
            all_due = data.get("due_tasks", []) + data.get("overdue_tasks", [])
            if all_due:
                print("   Sample tasks:")
                for task in all_due[:3]:
                    title = task.get("title", "")
                    due = task.get("due", "")[:10] if task.get("due") else ""
                    due_time = task.get("kirishima_due_time", "")
                    print(f"     - {title} (due: {due} {due_time})")
        
        return result["success"]
    
    def cleanup(self):
        """Clean up test data."""
        print("\n🧹 Cleaning Up Test Data")
        
        success = True
        
        # Delete test tasks
        for task_id in self.test_task_ids:
            result = self.make_request("DELETE", f"/tasks/stickynotes/{task_id}")
            self.print_result(f"Delete Task {task_id[:8]}...", result)
            success = success and result["success"]
        
        # Delete test task list
        if self.test_task_list_id:
            result = self.make_request("DELETE", f"/tasks/tasklists/{self.test_task_list_id}")
            self.print_result("Delete Test Task List", result)
            success = success and result["success"]
        
        return success


def main():
    """Main function."""
    # Parse command line arguments
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = sys.argv[2] if len(sys.argv) > 2 else "4215"
    
    base_url = f"http://{host}:{port}"
    
    print("="*60)
    print("🚀 Google Tasks API Simple Test Suite")
    print(f"Testing endpoint: {base_url}")
    print("="*60)
    
    client = SimpleTasksTestClient(base_url)
    
    # Run tests
    tests = [
        ("API Validation", client.test_validation),
        ("Monitor Status", client.test_monitor_status),
        ("Task Lists", client.test_task_lists),
        ("List Tasks", client.test_list_tasks),
        ("Stickynotes", client.test_stickynotes),
        ("Task Operations", client.test_task_operations),
        ("Due Tasks", client.test_due_tasks),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Cleanup
    try:
        client.cleanup()
    except Exception as e:
        print(f"⚠️  Cleanup failed: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
