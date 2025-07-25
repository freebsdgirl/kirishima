"""
Natural Language Processing Routes for Google API

This module defines the API endpoint for processing natural language queries
and converting them into structured Google API actions.

Endpoints:
    - POST /nlp: Process a natural language query and execute the appropriate Google service action

All endpoints handle exceptions and return appropriate HTTP error responses.
"""

from fastapi import APIRouter, HTTPException
from shared.models.googleapi import NaturalLanguageRequest, NaturalLanguageResponse

from app.services.nlp import parse_natural_language_query, execute_google_action

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

router = APIRouter()


@router.post("/nlp", response_model=NaturalLanguageResponse)
async def process_natural_language_query(request: NaturalLanguageRequest):
    """
    Process a natural language query and execute the appropriate Google service action.
    
    This endpoint:
    1. Sends the query to an LLM via the proxy service to parse intent and parameters
    2. Maps the LLM response to the appropriate Google service (Gmail, Calendar, Contacts)
    3. Executes the requested action with the parsed parameters
    4. Returns the result in a structured format
    
    Args:
        request: Natural language request containing the user's query
        
    Returns:
        NaturalLanguageResponse: Result of processing and executing the query
        
    Raises:
        HTTPException: If parsing fails, service is unavailable, or action execution fails
    """
    try:
        logger.info(f"Processing natural language query: {request.query}")
        
        # Step 1: Parse the natural language query using LLM
        parsed_action = await parse_natural_language_query(request.query)
        logger.info(f"Parsed action: {parsed_action.service}.{parsed_action.action}")
        
        # Step 2: Execute the parsed action
        result = await execute_google_action(parsed_action)
        logger.info(f"Action executed successfully")
        
        # Step 3: Return success response
        return NaturalLanguageResponse(
            success=True,
            action_taken=parsed_action,
            result=result
        )
        
    except HTTPException as e:
        # Re-raise HTTP exceptions from lower layers
        logger.error(f"HTTP error processing query '{request.query}': {e.detail}")
        return NaturalLanguageResponse(
            success=False,
            error=e.detail
        )
        
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error processing query '{request.query}': {e}")
        return NaturalLanguageResponse(
            success=False,
            error=f"Unexpected error: {str(e)}"
        )
