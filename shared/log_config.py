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
import shared.config
import os
import sys

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
    udp_handler = GelfUdpHandler(host=shared.config.GREYLOG_HOST, port=shared.config.GREYLOG_PORT, _app_name=service_name_env, debug=True)

    udp_handler.setLevel(logging.DEBUG)
    logger.addHandler(udp_handler)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger
