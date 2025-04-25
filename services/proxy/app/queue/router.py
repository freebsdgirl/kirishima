"""
This module defines the FastAPI router for managing a proxy task queue.
It provides endpoints to enqueue tasks (with support for both blocking and non-blocking modes),
check the status of the entire queue, and retrieve the status of individual tasks. The queue
supports task prioritization, optional callback URLs for non-blocking tasks, and timeout handling
for blocking tasks.
Endpoints:
    - POST /queue/enqueue: Enqueue a new task to the proxy queue.
    - GET /queue/status: Retrieve the current status and contents of the queue.
    - GET /queue/task/{task_id}: Retrieve the status and result (if available) of a specific task.
Models:
    - EnqueueTaskRequest: Request schema for enqueuing tasks.
    - EnqueueTaskResponse: Response schema for task enqueue operations.
    - TaskStatusResponse: Response schema for individual task status.
    - QueueTaskInfo: Information about a task in the queue.
    - QueueStatusResponse: Status and contents of the queue.
    - ProxyTask: Internal representation of a task.
    - ProxyTaskQueue: In-memory queue manager for proxy tasks.
Exceptions:
    - HTTPException 504: Raised if a blocking task times out.
    - HTTPException 404: Raised if a requested task is not found in the queue.

"""

from shared.models.queue import EnqueueTaskRequest, EnqueueTaskResponse, TaskStatusResponse, QueueTaskInfo, QueueStatusResponse, ProxyTask, ProxyTaskQueue

import uuid
import asyncio

from fastapi import APIRouter, HTTPException, status, Request
router = APIRouter()

queue = ProxyTaskQueue()


@router.post("/queue/enqueue", response_model=EnqueueTaskResponse)
async def enqueue_task(req: EnqueueTaskRequest, request: Request):
    """
    Enqueue a task to the proxy task queue.

    This endpoint allows clients to submit tasks for processing, supporting both blocking and 
    non-blocking task submission. For blocking tasks, the endpoint will wait for the task 
    to complete and return the result. For non-blocking tasks, it will immediately return 
    a task ID for future status tracking.

    Args:
        req (EnqueueTaskRequest): Task submission details including priority, payload, 
                                blocking status, and optional callback URL.
        request (Request): FastAPI request object.

    Returns:
        EnqueueTaskResponse: Contains task ID, enqueue status, and optional result for 
                            blocking tasks.

    Raises:
        HTTPException: 504 error if a blocking task times out after 2 minutes.
    """
    task_id = str(uuid.uuid4())
    future = asyncio.Future() if req.blocking else None

    # For non-blocking, implement callback logic here
    def callback(result):
        # Placeholder: send result to callback_url (e.g., via HTTP POST)
        # implement this later
        pass

    task = ProxyTask(
        priority=req.priority,
        task_id=task_id,
        payload=req.payload,
        blocking=req.blocking,
        future=future,
        callback=callback if (not req.blocking and req.callback_url) else None
    )
    await queue.enqueue(task)

    if req.blocking:
        try:
            # Wait for the result (worker must set future result)
            result = await asyncio.wait_for(future, timeout=120)  # 2 min timeout
            queue.remove_task(task_id)
            return EnqueueTaskResponse(
                task_id=task_id,
                enqueued=True,
                message="Task completed", result=result
            )
        except asyncio.TimeoutError:
            queue.remove_task(task_id)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Task timed out"
            )
    else:
        return EnqueueTaskResponse(
            task_id=task_id,
            enqueued=True,
            message="Task enqueued (non-blocking)"
        )


@router.get("/queue/status", response_model=QueueStatusResponse)
async def queue_status():
    """
    Retrieve the current status of the task queue.

    This endpoint provides an overview of the current state of the task queue, including
    the total number of tasks and details about each task in the queue.

    Returns:
        QueueStatusResponse: Contains the total queue size and a list of task information,
        including task IDs, priorities, blocking status, and creation times.
    """
    tasks = [
        QueueTaskInfo(
            task_id=t.task_id,
            priority=t.priority,
            blocking=t.blocking,
            created_at=t.created_at
        ) for t in queue.all_tasks()
    ]
    return QueueStatusResponse(
        queue_size=queue.queue_size(),
        tasks=tasks
    )


@router.get("/queue/task/{task_id}", response_model=TaskStatusResponse)
async def task_status(task_id: str):
    """
    Retrieve the status of a specific task by its task ID.

    This endpoint allows checking the current status of a task in the queue. 
    It returns the task's status (pending or completed) and optionally the result 
    if the task is a blocking task and has completed.

    Args:
        task_id (str): The unique identifier of the task to retrieve.

    Returns:
        TaskStatusResponse: Contains the task's ID, current status, and result (if applicable).

    Raises:
        HTTPException: 404 error if the task is not found in the queue.
    """
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    status_str = "pending"
    result = None
    if task.blocking and task.future and task.future.done():
        status_str = "completed"
        result = task.future.result()

    return TaskStatusResponse(
        task_id=task_id,
        status=status_str,
        result=result
    )
