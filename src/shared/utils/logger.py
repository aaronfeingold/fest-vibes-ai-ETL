"""
Centralized logging configuration for the application.
"""

import logging
import sys
from typing import Optional

# Log format that includes timestamp, log level, module name, and message
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    stream: bool = True,
) -> logging.Logger:
    """
    Set up a logger with consistent formatting and configuration.

    Args:
        name: Name of the logger (typically __name__)
        level: Logging level (default: INFO)
        log_file: Optional path to log file. If None, logs only to stdout
        stream: Whether to log to stdout (default: True)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if stream:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger("ajf_live_re_wire")
