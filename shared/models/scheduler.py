"""
This module defines Pydantic models for scheduling jobs and representing scheduled job responses.
Classes:
    SchedulerJobRequest: Represents a request to schedule a job with configurable execution parameters, including external URL, trigger type, run date, interval, and metadata.
    JobResponse: Represents the response details of a scheduled job, including job ID, next run time, trigger type, and associated metadata.
    SchedulerCallbackRequest: Represents a request payload for a scheduler callback with metadata and execution timestamp.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class SchedulerJobRequest(BaseModel):
    """
    Represents a request to schedule a job with configurable execution parameters.
    
    Attributes:
        external_url (str): The URL of the external service or endpoint to be triggered.
        trigger (str): The type of job scheduling trigger, either 'date', 'interval', or 'cron'.
        run_date (Optional[str]): An ISO datetime string specifying the exact time to run the job.
        interval_minutes (Optional[int]): Number of minutes between job executions for interval-based triggers.
        hour (Optional[int]): Hour of the day (0-23) for cron-based triggers.
        minute (Optional[int]): Minute of the hour (0-59) for cron-based triggers.
        day (Optional[int]): Day of the month (1-31) for cron-based triggers.
        day_of_week (Optional[str]): Day(s) of the week for cron-based triggers (e.g., 'mon-fri').
        metadata (Optional[Dict[str, Any]]): Additional key-value metadata associated with the job.
    """
    id: str                                 = Field(default_factory=lambda: str(uuid.uuid4()))
    external_url: str                       = Field(..., description="The URL of the external service or endpoint to be triggered.")
    trigger: str                            = Field(..., description="The type of job scheduling trigger, either 'date', 'cron', or 'interval'.")
    run_date: Optional[str]                 = Field(None, description="An ISO datetime string specifying the exact time to run the job.")
    interval_minutes: Optional[int]         = Field(None, description="Number of minutes between job executions for interval-based triggers.")
    hour: Optional[int]                     = Field(None, description="Hour of the day (0-23) for cron-based triggers.")
    minute: Optional[int]                   = Field(None, description="Minute of the hour (0-59) for cron-based triggers.")
    day: Optional[int]                      = Field(None, description="Day of the month (1-31) for cron-based triggers.")
    day_of_week: Optional[str]              = Field(None, description="Day(s) of the week for cron-based triggers (e.g., 'mon-fri').")
    metadata: Optional[Dict[str, Any]]      = Field(None, description="Additional key-value metadata associated with the job.")


class JobResponse(BaseModel):
    """
    Response model representing the details of a scheduled job.
    
    Attributes:
        job_id (str): Unique identifier for the scheduled job.
        next_run_time (Optional[datetime]): Timestamp of the next scheduled job execution.
        trigger (str): Type of job trigger ('date' or 'interval').
        metadata (Dict[str, Any]): Additional metadata associated with the job.
    """
    job_id: str                             = Field(..., description="Unique identifier for the scheduled job.")
    next_run_time: Optional[datetime]       = Field(None, description="Timestamp of the next scheduled")
    trigger: str                            = Field(..., description="Type of job trigger ('date' or 'interval').")
    metadata: Dict[str, Any]                = Field(..., description="Additional metadata associated with the job.")


class SchedulerCallbackRequest(BaseModel):
    """
    Represents a request payload for a scheduler callback with metadata and execution timestamp.
    
    Attributes:
        metadata (Dict[str, Any]): A dictionary containing arbitrary metadata associated with the scheduled job.
        executed_at (str): An ISO 8601 formatted timestamp indicating when the job was executed.
    """
    metadata: Dict[str, Any]                = Field(..., description="A dictionary containing arbitrary metadata associated with the scheduled job.")
    executed_at: str                        = Field(..., description="An ISO 8601 formatted timestamp indicating when the job was executed.")