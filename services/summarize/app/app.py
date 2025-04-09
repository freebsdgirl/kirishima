"""
This module defines the FastAPI application for the summarization service, including
routes for buffer management, summary generation, and user context retrieval.
The application provides the following functionalities:
- Health check endpoint (`/ping`) to verify the service status.
- Context retrieval endpoint (`/context/{user_id}`) to fetch user-specific buffers and summaries.
- Summarization endpoint (`/summarize_buffers`) to process and summarize buffer entries.
- Modular routing for buffer, summary, and documentation-related API endpoints.
Key Components:
- `get_context`: Retrieves user-specific buffers and summaries.
- `summarize_buffers`: Processes all buffer entries, generates summaries, and manages cleanup.
- `summarize_buffer_entries`: Summarizes a list of text entries using a local API.
Dependencies:
- `shared.log_config`: Provides logging configuration.
- `app.buffer`: Contains buffer-related utility functions and router.
- `app.summary`: Contains summary-related utility functions, types, and router.
- `app.docs`: Contains documentation-related router.
- `requests`: Used for making HTTP requests to the local summarization API.
- `fastapi`: Framework for building the API.
Error Handling:
- Uses `HTTPException` to handle and return appropriate HTTP status codes for errors.
- Logs errors for debugging and monitoring purposes.
Routes:
- `/ping`: Health check endpoint.
- `/context/{user_id}`: Retrieves user-specific context (buffers and summaries).
- `/summarize_buffers`: Summarizes all buffer entries and manages cleanup.
- `/summary`: Routes for summary-related operations.
- `/buffer`: Routes for buffer-related operations.
- `/docs`: Routes for API documentation.
"""
from shared.log_config import get_logger
logger = get_logger(__name__)


"""
Import utility functions for managing user buffers and summaries:
- Buffer-related functions: get_all_buffers, get_buffer, delete_buffer
- Summary-related functions: add_summary, get_user_summary
- SummarizeRequest type for handling summarization requests
"""
from app.buffer import get_all_buffers, get_buffer, delete_buffer
from app.summary import add_summary, get_user_summary, SummarizeRequest


from typing import Dict, Any, List
import requests


"""
FastAPI application instance for the summarization service.

This application serves as the main entry point for the summarization API,
handling routes for buffer management, summary generation, and user context retrieval.
"""
from fastapi import FastAPI, HTTPException, status
app = FastAPI()

@app.get("/ping")
def ping():
    return {"status": "ok"}


"""
Include routers for buffer and summary endpoints with specific prefixes and tags.

This configuration sets up two separate routers for the application:
- The summary router is mounted at the "/summary" path with "summary" tags
- The buffer router is mounted at the "/buffer" path with "buffer" tags

These routers provide modular routing for buffer and summary-related API endpoints.
"""
from app.buffer import router as buffer_router
from app.summary import router as summary_router
from app.docs import router as docs_router
app.include_router(summary_router, prefix="/summary", tags=["summary"])
app.include_router(buffer_router, prefix="/buffer", tags=["buffer"])
app.include_router(docs_router)


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
