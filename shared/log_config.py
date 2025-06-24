"""
This module provides a utility function for creating and configuring a logger
that sends logs to a Graylog server using the GELF (Graylog Extended Log Format) protocol.

The logger is configured with a UDP handler by default and uses the environment
variable `SERVICE_NAME` to set the application name in the log messages.

Dependencies:
    - logging: Standard Python logging module.
    - pygelf: A library for sending logs to Graylog in GELF format.
    - shared.config: A shared configuration module (assumed to be part of the project).
    - os: Standard Python module for interacting with the operating system.

Functions:
    - get_logger(service_name: str) -> logging.Logger:
"""

import logging
from pygelf import GelfUdpHandler, GelfTcpHandler
import os
import json

with open('/app/config/config.json') as f:
    _config = json.load(f)
GRAYLOG = _config["graylog"]


def get_logger(service_name: str) -> logging.Logger:
    """
    Creates and configures a logger for the specified service.

    This function initializes a logger with the given service name, sets its
    logging level to DEBUG, and attaches a GELF UDP handler for sending logs
    to a Graylog server. The handler is configured using the environment
    variable `SERVICE_NAME` to set the application name.

    Args:
        service_name (str): The name of the service for which the logger is created.

    Returns:
        logging.Logger: A configured logger instance.
    """

    service_name_env = os.getenv("SERVICE_NAME")

    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)
    udp_handler = GelfUdpHandler(host=GRAYLOG["host"], port=GRAYLOG['port'], _app_name=service_name_env, debug=True)

    logger.addHandler(udp_handler)

    return logger
