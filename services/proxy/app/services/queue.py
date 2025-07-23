
from app.services.send_to_ollama import send_to_ollama
from app.services.send_to_openai import send_to_openai
from app.services.send_to_anthropic import send_to_anthropic

from shared.models.queue import (
    EnqueueTaskRequest,
    EnqueueTaskResponse,
    TaskStatusResponse,
    QueueTaskInfo,
    QueueStatusResponse,
    ProxyTask,
    ProxyTaskQueue
)

from shared.models.proxy import OllamaRequest, OpenAIRequest, AnthropicRequest

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import uuid
import asyncio

from fastapi import APIRouter, HTTPException, status, Request
router = APIRouter()

# Provider-specific queues
ollama_queue = ProxyTaskQueue()
openai_queue = ProxyTaskQueue()
anthropic_queue = ProxyTaskQueue()

# Default queue for legacy compatibility (Ollama)
queue = ollama_queue


async def _enqueue_task(req: EnqueueTaskRequest, request: Request):
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


async def _queue_status():
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


async def _task_status(task_id: str):
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


async def queue_worker_main(queue: ProxyTaskQueue):
    """
    Process tasks from a ProxyTaskQueue by sending payloads to the correct provider.
    
    This async function continuously dequeues tasks from the provided queue, sends each task's 
    payload to Ollama, OpenAI, or Anthropic, and handles both blocking and non-blocking task types. For blocking tasks, 
    it sets the future's result or exception. For non-blocking tasks, it calls the provided callback.
    
    Args:
        queue (ProxyTaskQueue): The queue from which tasks will be dequeued and processed.
    
    Raises:
        Exception: If an error occurs during task processing, which is logged and potentially 
        set as an exception on the task's future for blocking tasks.
    """
    logger.debug("Queue worker started.")

    while True:
        task: ProxyTask = await queue.dequeue()
        logger.debug(f"Dequeued task {task.task_id} (priority={task.priority}, blocking={task.blocking})")

        try:
            # Dispatch based on payload type
            if isinstance(task.payload, OllamaRequest):
                result = await send_to_ollama(task.payload)
            elif isinstance(task.payload, OpenAIRequest):
                result = await send_to_openai(task.payload)
            elif isinstance(task.payload, AnthropicRequest):
                result = await send_to_anthropic(task.payload)
            else:
                raise Exception(f"Unknown payload type: {type(task.payload)}")

            if task.blocking and task.future:
                task.future.set_result(result)
                logger.debug(f"Set result for blocking task {task.task_id}")

            elif not task.blocking and task.callback:
                task.callback(result)
                logger.debug(f"Called callback for non-blocking task {task.task_id}")

        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {e}")
            if task.blocking and task.future and not task.future.done():
                task.future.set_exception(e)

        finally:
            queue.remove_task(task.task_id)
# In your main app startup, you should start a worker for each queue, e.g.:
# asyncio.create_task(queue_worker_main(ollama_queue))
# asyncio.create_task(queue_worker_main(openai_queue))
# asyncio.create_task(queue_worker_main(anthropic_queue))   