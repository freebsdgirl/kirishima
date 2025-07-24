#!/usr/bin/env python3
"""
Google Tasks API Test Script

Tests all Google Tasks functionality in the googleapi microservice.
Run this script to verify that all endpoints are working correctly.

Usage:
    python test_google_tasks.py [--host HOST] [--port PORT]

Examples:
    python test_google_tasks.py
    python test_google_tasks.py --host localhost --port 8000
    python test_google_tasks.py --host googleapi --port 8000
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class GoogleTasksTestClient:
    """Test client for Google Tasks API endpoints."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_task_list_id: Optional[str] = None
        self.test_task_ids: list = []
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request and return JSON response."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.request(method, url, **kwargs)
            
            # Try to parse JSON response
            try:
                data = response.json()
            except:
                data = {"status_code": response.status_code, "text": response.text}
            
            return {
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "data": data
            }
            
        except Exception as e:
            return {
                "status_code": 0,
                "success": False,
                "error": str(e)
            }
    
    def print_result(self, test_name: str, result: Dict[str, Any]):
        """Print test result in a formatted way."""
        if result["success"]:
            console.print(f"✅ {test_name}", style="green")
            if "data" in result and isinstance(result["data"], dict):
                # Print relevant response data
                data = result["data"]
                if "message" in data:
                    console.print(f"   {data['message']}", style="dim")
                elif "success" in data and not data["success"]:
                    console.print(f"   API Error: {data.get('message', 'Unknown error')}", style="red")
        else:
            console.print(f"❌ {test_name}", style="red")
            if "error" in result:
                console.print(f"   Error: {result['error']}", style="red")
            elif "data" in result:
                console.print(f"   Response: {result['data']}", style="red")
    
    async def test_validation(self):
        """Test Google Tasks API validation."""
        console.print("\n🔍 Testing API Validation", style="bold blue")
        
        result = await self.make_request("GET", "/tasks/validate")
        self.print_result("API Validation", result)
        
        return result["success"]
    
    async def test_monitor_status(self):
        """Test monitor status endpoint."""
        console.print("\n📊 Testing Monitor Status", style="bold blue")
        
        result = await self.make_request("GET", "/tasks/monitor/status")
        self.print_result("Monitor Status", result)
        
        if result["success"] and "data" in result:
            status = result["data"]
            table = Table(title="Monitor Status")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            for key, value in status.items():
                table.add_row(str(key), str(value))
            
            console.print(table)
    
    async def test_task_lists(self):
        """Test task list management."""
        console.print("\n📋 Testing Task Lists", style="bold blue")
        
        # 1. List existing task lists
        result = await self.make_request("GET", "/tasks/tasklists")
        self.print_result("List Task Lists", result)
        
        # 2. Create a new task list
        test_list_name = f"Test List {datetime.now().strftime('%H:%M:%S')}"
        result = await self.make_request("POST", "/tasks/tasklists", json={
            "title": test_list_name
        })
        self.print_result("Create Task List", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            self.test_task_list_id = data.get("task_list_id")
            console.print(f"   Created task list ID: {self.test_task_list_id}", style="dim")
        
        # 3. List task lists again to verify creation
        result = await self.make_request("GET", "/tasks/tasklists")
        self.print_result("List Task Lists (after creation)", result)
        
        return self.test_task_list_id is not None
    
    async def test_list_tasks(self):
        """Test adding tasks to custom lists."""
        if not self.test_task_list_id:
            console.print("⚠️  Skipping list tasks test - no test list available", style="yellow")
            return
        
        console.print("\n📝 Testing List Tasks", style="bold blue")
        
        # Add tasks to the test list
        test_tasks = [
            {"title": "Buy milk"},
            {"title": "Buy bread"},
            {"title": "Buy eggs", "notes": "Organic preferred"}
        ]
        
        for task_data in test_tasks:
            result = await self.make_request(
                "POST", 
                f"/tasks/tasklists/{self.test_task_list_id}/tasks",
                json=task_data
            )
            self.print_result(f"Add '{task_data['title']}' to list", result)
    
    async def test_stickynotes(self):
        """Test stickynotes (default task list) functionality."""
        console.print("\n🗒️  Testing Stickynotes", style="bold blue")
        
        # 1. List current stickynotes
        result = await self.make_request("GET", "/tasks/stickynotes")
        self.print_result("List Stickynotes", result)
        
        # 2. Create a simple task
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        simple_task = {
            "title": "Test simple task",
            "notes": "This is a test task",
            "due": tomorrow
        }
        
        result = await self.make_request("POST", "/tasks/stickynotes", json=simple_task)
        self.print_result("Create Simple Task", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            task_id = data.get("task_id")
            if task_id:
                self.test_task_ids.append(task_id)
        
        # 3. Create a task with due time
        timed_task = {
            "title": "Test timed task",
            "notes": "Task with specific time",
            "due": tomorrow,
            "due_time": "14:30"
        }
        
        result = await self.make_request("POST", "/tasks/stickynotes", json=timed_task)
        self.print_result("Create Timed Task", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            task_id = data.get("task_id")
            if task_id:
                self.test_task_ids.append(task_id)
        
        # 4. Create a recurring task
        today = datetime.now().strftime('%Y-%m-%d')
        recurring_task = {
            "title": "Test daily recurring task",
            "notes": "This task repeats daily",
            "due": today,
            "due_time": "09:00",
            "rrule": "FREQ=DAILY;INTERVAL=1"
        }
        
        result = await self.make_request("POST", "/tasks/stickynotes", json=recurring_task)
        self.print_result("Create Recurring Task", result)
        
        if result["success"] and "data" in result:
            data = result["data"]["data"] if "data" in result["data"] else result["data"]
            task_id = data.get("task_id")
            if task_id:
                self.test_task_ids.append(task_id)
        
        # 5. List stickynotes again to see new tasks
        result = await self.make_request("GET", "/tasks/stickynotes")
        self.print_result("List Stickynotes (after creation)", result)
        
        if result["success"] and "data" in result:
            tasks = result["data"]
            if tasks:
                table = Table(title="Current Stickynotes")
                table.add_column("Title", style="cyan")
                table.add_column("Due", style="green")
                table.add_column("Due Time", style="yellow")
                table.add_column("RRULE", style="magenta")
                
                for task in tasks[-3:]:  # Show last 3 tasks
                    table.add_row(
                        task.get("title", ""),
                        task.get("due", "")[:10] if task.get("due") else "",
                        task.get("kirishima_due_time", ""),
                        task.get("kirishima_rrule", "")
                    )
                
                console.print(table)
    
    async def test_task_operations(self):
        """Test task update and completion operations."""
        if not self.test_task_ids:
            console.print("⚠️  Skipping task operations test - no test tasks available", style="yellow")
            return
        
        console.print("\n⚙️  Testing Task Operations", style="bold blue")
        
        task_id = self.test_task_ids[0]
        
        # 1. Update a task
        update_data = {
            "title": "Updated test task",
            "notes": "This task has been updated"
        }
        
        result = await self.make_request("PUT", f"/tasks/stickynotes/{task_id}", json=update_data)
        self.print_result("Update Task", result)
        
        # 2. Complete a non-recurring task (if we have one)
        if len(self.test_task_ids) > 1:
            result = await self.make_request("POST", f"/tasks/stickynotes/{self.test_task_ids[1]}/complete")
            self.print_result("Complete Non-Recurring Task", result)
        
        # 3. Complete a recurring task (should update due date)
        if len(self.test_task_ids) > 2:
            result = await self.make_request("POST", f"/tasks/stickynotes/{self.test_task_ids[2]}/complete")
            self.print_result("Complete Recurring Task", result)
            
            if result["success"] and "data" in result and result["data"]:
                data = result["data"]["data"] if "data" in result["data"] else result["data"]
                if data and data.get("recurring"):
                    console.print(f"   Next due date: {data.get('next_due')}", style="dim")
    
    async def test_due_tasks(self):
        """Test due tasks endpoint (brain service integration)."""
        console.print("\n⏰ Testing Due Tasks", style="bold blue")
        
        result = await self.make_request("GET", "/tasks/due")
        self.print_result("Get Due Tasks", result)
        
        if result["success"] and "data" in result:
            data = result["data"]
            due_count = len(data.get("due_tasks", []))
            overdue_count = len(data.get("overdue_tasks", []))
            
            console.print(f"   Due tasks: {due_count}", style="green")
            console.print(f"   Overdue tasks: {overdue_count}", style="red" if overdue_count > 0 else "green")
            
            # Show a few due tasks if any
            all_due = data.get("due_tasks", []) + data.get("overdue_tasks", [])
            if all_due:
                table = Table(title="Due/Overdue Tasks")
                table.add_column("Title", style="cyan")
                table.add_column("Due Date", style="yellow")
                table.add_column("Due Time", style="green")
                
                for task in all_due[:5]:  # Show first 5
                    table.add_row(
                        task.get("title", ""),
                        task.get("due", "")[:10] if task.get("due") else "",
                        task.get("kirishima_due_time", "")
                    )
                
                console.print(table)
    
    async def cleanup(self):
        """Clean up test data."""
        console.print("\n🧹 Cleaning Up Test Data", style="bold blue")
        
        # Delete test tasks
        for task_id in self.test_task_ids:
            result = await self.make_request("DELETE", f"/tasks/stickynotes/{task_id}")
            self.print_result(f"Delete Task {task_id[:8]}...", result)
        
        # Delete test task list
        if self.test_task_list_id:
            result = await self.make_request("DELETE", f"/tasks/tasklists/{self.test_task_list_id}")
            self.print_result("Delete Test Task List", result)


async def run_all_tests(base_url: str):
    """Run all Google Tasks tests."""
    console.print(Panel.fit(
        f"🚀 Google Tasks API Test Suite\n\nTesting endpoint: {base_url}",
        title="Test Suite",
        border_style="blue"
    ))
    
    async with GoogleTasksTestClient(base_url) as client:
        # Test sequence
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
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True
                ) as progress:
                    task = progress.add_task(f"Running {test_name}...", total=None)
                    result = await test_func()
                    results.append((test_name, result))
            except Exception as e:
                console.print(f"❌ {test_name} failed with exception: {e}", style="red")
                results.append((test_name, False))
        
        # Cleanup
        try:
            await client.cleanup()
        except Exception as e:
            console.print(f"⚠️  Cleanup failed: {e}", style="yellow")
        
        # Summary
        console.print("\n" + "="*50, style="blue")
        console.print("📊 Test Summary", style="bold blue")
        console.print("="*50, style="blue")
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            console.print(f"{status} {test_name}")
        
        console.print(f"\nTotal: {passed}/{total} tests passed", 
                     style="green" if passed == total else "red")
        
        if passed == total:
            console.print("🎉 All tests passed!", style="bold green")
        else:
            console.print("⚠️  Some tests failed. Check the output above for details.", style="bold red")
        
        return passed == total


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test Google Tasks API endpoints")
    parser.add_argument("--host", default="localhost", help="API host (default: localhost)")
    parser.add_argument("--port", default="4215", help="API port (default: 4215)")
    parser.add_argument("--https", action="store_true", help="Use HTTPS instead of HTTP")
    
    args = parser.parse_args()
    
    scheme = "https" if args.https else "http"
    base_url = f"{scheme}://{args.host}:{args.port}"
    
    try:
        success = asyncio.run(run_all_tests(base_url))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        console.print("\n⚠️  Test suite interrupted by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ Test suite failed: {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
