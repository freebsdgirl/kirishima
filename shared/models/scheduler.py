from typing import Optional, Dict, Any
from pydantic import BaseModel


class SchedulerJobRequest(BaseModel):
    """
    Represents a request to schedule a job with configurable execution parameters.
    
    Attributes:
        external_url (str): The URL of the external service or endpoint to be triggered.
        trigger (str): The type of job scheduling trigger, either 'date' or 'interval'.
        run_date (Optional[str]): An ISO datetime string specifying the exact time to run the job.
        interval_minutes (Optional[int]): Number of minutes between job executions for interval-based triggers.
        metadata (Optional[Dict[str, Any]]): Additional key-value metadata associated with the job.
    """
    id: str
    external_url: str
    trigger: str  # 'date' or 'interval'
    run_date: Optional[str] = None  # ISO datetime string
    interval_minutes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = {}
