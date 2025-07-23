"""
Utility functions for Gmail service integration.

This module provides helper functions for loading configuration files and logging
within the Google API Gmail service context.

Functions:
    get_config(): Loads configuration data from a JSON file and returns it as a dictionary.
"""
import json

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")


def get_config():
    """Load configuration from config.json"""
    try:
        with open('/app/config/config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}