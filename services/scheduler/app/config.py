# SQLite database connection URL for storing job-related data
"""
This module contains configuration settings for the scheduler service.

Attributes:
    SCHEDULER_DB (str): The relative file path to the SQLite database used 
    for storing job-related data.
"""

SCHEDULER_DB                             = "./shared/db/scheduler/scheduler.db"