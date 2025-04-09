from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    """
    Represents a request for summarizing text with optional database storage.
    
    Attributes:
        save (bool): Flag to determine whether the summary should be saved in a database. Defaults to True.
        timestamp (str): Timestamp of the summary request, automatically set to the current UTC time.
        text (str): The text content to be summarized.
        platform (str): Comma-separated list of platforms associated with the summary.
        user_id (str): Unique identifier of the user from the contacts microservice.
    """
    save: bool = Field(default=True)    # Whether to save the summary in a database
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())  # Timestamp of the request
    text: str                           # text to summarize
    platform: str                       # comma separated list of platforms
    user_id: str                        # uuid from contacts microservice
