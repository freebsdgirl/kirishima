"""
This module provides a utility function to create a logger configured for sending logs to Graylog.
The logger is set up with a GELF (Graylog Extended Log Format) UDP handler, allowing logs to be sent
to a Graylog server with service-specific metadata. The configuration for the Graylog server and log
level is sourced from the `shared.config` module.
Dependencies:
    - logging: Python's built-in logging module.
    - graypy: A Python library for sending logs to Graylog.
    - shared.config: A custom module containing configuration settings for the application.
Functions:
    - get_logger(service_name: str) -> logging.Logger:
        Creates and returns a logger configured for Graylog with the specified service name.
"""
import logging

import shared.config as config

import graypy


def get_logger(service_name: str) -> logging.Logger:
    """
    Create a logger configured for Graylog with a specified service name.
    
    Args:
        service_name (str): The name of the service for which the logger is being created.
    
    Returns:
        logging.Logger: A configured logger that sends logs to Graylog via UDP with service-specific metadata.
    
    The logger is set up with a GELF (Graylog Extended Log Format) UDP handler, using configuration
    from the shared config module. The log level can be specified as either a string or numeric value.
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)

    gelf_handler = graypy.GELFUDPHandler(config.GREYLOG_HOST, config.GREYLOG_PORT)
    gelf_handler.extra_fields = {
        'service': service_name
    }

    # Determine the log level from the config variable.
    # This allows for either a string (like "DEBUG") or a numeric value (like 10).
    level = config.GREYLOG_LOG_LEVEL
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    gelf_handler.setLevel(level)

    logger.addHandler(gelf_handler)

    return logger
