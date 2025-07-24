"""
Google Tasks monitoring service.
Monitors stickynotes tasks for due/overdue items and can notify the brain service.
"""

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

import asyncio
import json
from typing import Dict, Any, Set, Optional
from datetime import datetime

from .tasks import get_due_tasks
from .util import get_config

class TasksMonitor:
    """
    Monitors stickynotes tasks for due/overdue items.
    Runs on a configurable interval and can notify the brain service.
    """
    
    def __init__(self):
        self.running = False
        self.last_check = None
        self.seen_due_tasks: Set[str] = set()
        self.poll_interval = 60  # Default 60 seconds
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration."""
        config = get_config()
        return config.get('tasks', {}).get('monitor', {})
    
    async def start_monitoring(self):
        """Start the tasks monitoring loop."""
        if self.running:
            logger.warning("Tasks monitoring is already running")
            return
        
        config = self.load_config()
        self.poll_interval = config.get('poll_interval', 60)
        
        logger.info(f"Starting tasks monitoring with {self.poll_interval}s interval")
        self.running = True
        
        try:
            while self.running:
                await self.check_due_tasks()
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            logger.info("Tasks monitoring cancelled")
        except Exception as e:
            logger.error(f"Tasks monitoring error: {e}")
        finally:
            self.running = False
            logger.info("Tasks monitoring stopped")
    
    async def check_due_tasks(self):
        """Check for due tasks and optionally notify brain service."""
        try:
            self.last_check = datetime.utcnow().isoformat()
            
            # Get due tasks
            due_response = get_due_tasks()
            if not due_response.success:
                logger.error("Failed to get due tasks")
                return
            
            all_due_tasks = due_response.due_tasks + due_response.overdue_tasks
            current_due_ids = {task.id for task in all_due_tasks}
            
            # Find newly due tasks
            new_due_tasks = [
                task for task in all_due_tasks 
                if task.id not in self.seen_due_tasks
            ]
            
            if new_due_tasks:
                logger.info(f"Found {len(new_due_tasks)} newly due tasks")
                
                # Update seen tasks
                self.seen_due_tasks.update(task.id for task in new_due_tasks)
            
            # Remove tasks that are no longer due
            self.seen_due_tasks &= current_due_ids
            
        except Exception as e:
            logger.error(f"Error checking due tasks: {e}")
    
    def stop_monitoring(self):
        """Stop the tasks monitoring."""
        if self.running:
            logger.info("Stopping tasks monitoring")
            self.running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitoring status."""
        return {
            "running": self.running,
            "last_check": self.last_check,
            "seen_due_tasks_count": len(self.seen_due_tasks),
            "poll_interval": self.poll_interval
        }


# Global monitor instance
_tasks_monitor: Optional[TasksMonitor] = None


async def start_tasks_monitoring():
    """Start the global tasks monitoring service."""
    global _tasks_monitor
    
    if _tasks_monitor and _tasks_monitor.running:
        logger.warning("Tasks monitoring is already running")
        return
    
    _tasks_monitor = TasksMonitor()
    await _tasks_monitor.start_monitoring()


def stop_tasks_monitoring():
    """Stop the global tasks monitoring service."""
    global _tasks_monitor
    
    if _tasks_monitor:
        _tasks_monitor.stop_monitoring()


def get_monitor_status() -> Dict[str, Any]:
    """Get the current status of the tasks monitor."""
    global _tasks_monitor
    
    if _tasks_monitor:
        return _tasks_monitor.get_status()
    
    return {
        "running": False,
        "last_check": None,
        "seen_due_tasks_count": 0,
        "poll_interval": 60
    }
