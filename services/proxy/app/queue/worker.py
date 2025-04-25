"""
This module defines the queue worker logic for processing ProxyTaskQueue tasks by sending payloads to the Ollama API.
Functions:
    send_to_ollama(payload):
        Asynchronously sends a payload to the Ollama API's generate endpoint, handling HTTP and connection errors,
        and returns the API response.
    queue_worker_main(queue: ProxyTaskQueue):
        Continuously processes tasks from a ProxyTaskQueue by sending their payloads to Ollama, handling both blocking
        and non-blocking tasks, and managing task results or callbacks accordingly.
"""

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

from shared.models.queue import ProxyTaskQueue, ProxyTask
import httpx
import json
import app.config
from fastapi import HTTPException, status


async def send_to_ollama(payload):
    """
    Send a payload to the Ollama API for generation.
    
    Sends an asynchronous HTTP POST request to the Ollama API's generate endpoint with the provided payload.
    Handles potential HTTP and request errors, logging details and raising appropriate HTTPExceptions.
    
    Args:
        payload (dict): The payload to send to the Ollama API for generation.
    
    Returns:
        httpx.Response: The response from the Ollama API containing the generated content.
    
    Raises:
        HTTPException: If there are HTTP status errors or connection issues with the Ollama API.
    """
    logger.debug(f"Request to Ollama API:\n{json.dumps(payload, indent=4, ensure_ascii=False)}")

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{app.config.OLLAMA_URL}/api/generate",
                json=payload
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from Ollama API: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from language model service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to Ollama API: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )

    json_response = response.json()
    logger.debug(f"Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    return response


async def queue_worker_main(queue: ProxyTaskQueue):
    """
    Process tasks from a ProxyTaskQueue by sending payloads to Ollama.
    
    This async function continuously dequeues tasks from the provided queue, sends each task's 
    payload to Ollama, and handles both blocking and non-blocking task types. For blocking tasks, 
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
            result = await send_to_ollama(task.payload)
    
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