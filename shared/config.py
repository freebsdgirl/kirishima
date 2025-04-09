"""
Configuration settings for Greylog logging.

Defines the host, port, and log level for UDP-based GELF (Graylog Extended Log Format) logging.
"""
GREYLOG_HOST                    = "localhost"   # GELF UDP host
GREYLOG_PORT                    = 12201         # GELF UDP port
GREYLOG_LOG_LEVEL               = "DEBUG"       # DEBUG INFO WARNING ERROR CRITICAL

