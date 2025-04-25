from pydantic import BaseModel, Field
from typing import Any, Optional, List

class QueueTaskInfo(BaseModel):
    """
    Represents a single task's info in the queue for status monitoring.
    """
    task_id: str
    priority: int
    blocking: bool
    created_at: float

class QueueStatusResponse(BaseModel):
    """
    Represents the response for /queue/status endpoint.
    """
    queue_size: int = Field(..., description="Number of tasks currently in the queue.")
    tasks: List[QueueTaskInfo] = Field(..., description="List of tasks currently tracked in the queue.")




class EnqueueTaskRequest(BaseModel):
    priority: int = Field(..., description="Lower = higher priority (e.g., 0 is highest)")
    payload: Any = Field(..., description="Task payload (prompt, user info, etc)")
    blocking: bool = Field(..., description="If true, waits for result; if false, returns immediately")
    # For non-blocking: optional callback URL
    callback_url: Optional[str] = Field(None, description="Callback URL for non-blocking tasks")

class EnqueueTaskResponse(BaseModel):
    task_id: str
    enqueued: bool
    message: str
    # For blocking: result (if available)
    result: Optional[Any] = None

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None



import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

@dataclass(order=True)
class ProxyTask:
    """
    Represents a task to be sent to Ollama.
    Tasks are ordered by priority (lower value = higher priority).
    """
    priority: int
    task_id: str = field(compare=False)
    payload: Any = field(compare=False)
    blocking: bool = field(compare=False)
    created_at: float = field(default_factory=time.time, compare=False)
    # For blocking tasks: a Future to set the result on
    future: Optional[asyncio.Future] = field(default=None, compare=False)
    # For non-blocking tasks: a callback function or URL
    callback: Optional[Callable[[Any], None]] = field(default=None, compare=False)


class ProxyTaskQueue:
    """
    An asyncio-based priority queue for ProxyTasks.
    Handles both blocking and non-blocking tasks.
    """
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._tasks = {}  # task_id -> ProxyTask (for status/lookup)

    async def enqueue(self, task: ProxyTask):
        """Add a task to the queue."""
        await self._queue.put(task)
        self._tasks[task.task_id] = task

    async def dequeue(self) -> ProxyTask:
        """Remove and return the highest-priority task."""
        task = await self._queue.get()
        self._queue.task_done()
        return task

    def get_task(self, task_id: str) -> Optional[ProxyTask]:
        """Get a task by its ID (for status, etc)."""
        return self._tasks.get(task_id)

    def remove_task(self, task_id: str):
        """Remove a task from the lookup (after completion)."""
        self._tasks.pop(task_id, None)

    def queue_size(self) -> int:
        """Return the number of tasks in the queue."""
        return self._queue.qsize()

    def all_tasks(self):
        """Return all tasks currently tracked (for monitoring)."""
        return list(self._tasks.values())