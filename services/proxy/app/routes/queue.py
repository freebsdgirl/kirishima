
from app.services.queue import _enqueue_task, _queue_status, _task_status

from shared.models.queue import EnqueueTaskRequest, EnqueueTaskResponse, TaskStatusResponse, QueueStatusResponse

from fastapi import APIRouter, Request
router = APIRouter()


@router.post("/enqueue", response_model=EnqueueTaskResponse)
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
    return await _enqueue_task(req, request)


@router.get("/status", response_model=QueueStatusResponse)
async def queue_status():
    """
    Retrieve the current status of the task queue.

    This endpoint provides an overview of the current state of the task queue, including
    the total number of tasks and details about each task in the queue.

    Returns:
        QueueStatusResponse: Contains the total queue size and a list of task information,
        including task IDs, priorities, blocking status, and creation times.
    """
    return await _queue_status()


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def task_status(task_id: str):
    """
    Retrieve the status of a specific task by its task ID.

    This endpoint allows clients to check the status of a task in the queue, including
    whether it is pending or completed, and to retrieve the result if it is a blocking task.

    Args:
        task_id (str): The unique identifier of the task to retrieve.

    Returns:
        TaskStatusResponse: Contains the task's ID, current status, and result (if applicable).

    Raises:
        HTTPException: 404 error if the task is not found in the queue.
    """
    return await _task_status(task_id)