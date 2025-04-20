"""
This module defines a FastAPI application for managing and summarizing user-specific buffers and summaries. 
The application includes the following functionalities:
- Health check endpoint to verify service status.
- Endpoint to list all registered API routes.
- Endpoint to retrieve user context, including buffers and summaries.
- Endpoint to summarize all user buffer entries, group them by user, and manage buffer cleanup.
- Utility function to summarize text entries using a local Ollama API.
Modules and Dependencies:
- `app.buffer`: Handles buffer-related operations and routing.
- `app.summary`: Manages summary-related operations and routing.
- `app.docs`: Provides API documentation routing.
- `shared.log_config`: Configures logging for the application.
- `fastapi`: Framework for building the API.
- `requests`: Used for making HTTP requests to the local Ollama API.
- `typing`: Provides type annotations for better code clarity.
Endpoints:
1. `/ping`: Health check endpoint.
2. `/__list_routes__`: Lists all registered API routes.
3. `/context/{user_id}`: Retrieves user-specific buffers and summaries.
4. `/summarize_buffers`: Processes and summarizes all user buffer entries.
Utility Function:
- `summarize_buffer_entries`: Summarizes a list of text entries into a single paragraph using a local API.
Error Handling:
- Logs errors and raises HTTP exceptions for failed operations.
"""

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.log_config import get_logger
logger = get_logger(__name__)

from app.buffer import get_all_buffers, get_buffer, delete_buffer
from app.summary import add_summary, get_user_summary, SummarizeRequest

from typing import Dict, Any, List
import requests

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI, HTTPException, status

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="summarize")


@app.get("/context/{user_id}", response_model=Dict[str, Any])
def get_context(user_id: str) -> Dict[str, Any]:
    """
    Retrieve user context by fetching user-specific buffers and summaries.

    Endpoint to get all buffer entries and summaries for a specific user.
    Returns a dictionary containing the user's buffers and summaries.

    Args:
        user_id (str): The unique identifier of the user.

    Returns:
        Dict[str, Any]: A dictionary with 'buffers' and 'summaries' for the user.

    Raises:
        HTTPException: If there is an error retrieving the user's context.
    """
    try:
        user_buffers = get_buffer(user_id)
        user_summaries = get_user_summary(user_id)

    except Exception as e:
        logger.error(f"Error retrieving context for user {user_id}: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user context"
        )

    return {
        "buffers": user_buffers,
        "summaries": user_summaries
    }


@app.post("/summarize_buffers", response_model=Dict[str, Any])
def summarize_buffers() -> Dict[str, Any]:
    """
    Endpoint to process and summarize all user buffer entries.

    Aggregates buffer entries by user, generates summaries, and manages buffer cleanup:
    - Retrieves all buffer entries
    - Groups entries by user ID
    - Generates a summary for each user's entries
    - Stores summaries using add_summary
    - Deletes processed buffer entries

    Returns a dictionary with summarization results for each user, including summary IDs
    or error information if processing fails.

    Raises HTTPException if buffer retrieval fails.
    """
    try:
        buffers = get_all_buffers()

    except Exception as e:
        logger.error(f"Error fetching buffers: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve buffers for summarization"
        )
    
    if not buffers:
        return {
            "message": "No buffers to summarize."
        }
    
    # Group buffer entries by user_id
    grouped_buffers: Dict[str, List] = {}
    for entry in buffers:
        grouped_buffers.setdefault(entry.user_id, []).append(entry)

    results = {}

    for user_id, entries in grouped_buffers.items():
        # Extract texts and platforms from entries
        texts = [entry.text for entry in entries]

        # Ensure platforms are concatenated into a comma-separated string (unique values)
        unique_platforms = {entry.platform for entry in entries if entry.platform}
        platforms_str = ", ".join(unique_platforms)
        
        # Call the stub summarization function
        summary_text = summarize_buffer_entries(texts)
        
        # Create a summary request object
        summary_req = SummarizeRequest(
            text=summary_text,
            platform=platforms_str,
            user_id=user_id
        )
        
        try:
            summary_resp = add_summary(summary_req)
            delete_resp = delete_buffer(user_id)
            results[user_id] = {"summary_id": summary_resp.id, "deleted": delete_resp.deleted}

        except Exception as e:
            logger.error(f"Error processing summarization for user {user_id}: {e}")
            results[user_id] = {"error": "An error occurred while processing the summarization."}
    return results


def summarize_buffer_entries(texts: List[str]) -> str:
    """
    Summarize a list of text entries into a single paragraph using a local Ollama API.
    
    Args:
        texts (List[str]): A list of text entries to be summarized.
    
    Returns:
        str: A concise summary of the input texts, or an empty string if summarization fails.
    """
    text = "\n".join(texts)

    prompt = f"""Summarize the following conversation in a single paragraph:


    [START CONVERSATION]

    {text}

    [END CONVERSATION]


    Summarize the previous conversation in a single descriptive paragraph.
    Do not include commentary, apologies, system messages, or statements about being an AI.
    Only return the summary.
    """

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "deepseek:latest",
                "prompt": prompt,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

    except Exception as e:
        import logging
        logging.error(f"Error during summarization: {e}")
        return ""