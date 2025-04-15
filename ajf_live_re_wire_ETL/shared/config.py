"""
Configuration settings for the application.
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, Optional

import pytz


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define the timezone for New Orleans (CST/CDT),
# since current version is New Orleans' events specific
NEW_ORLEANS_TZ = pytz.timezone("America/Chicago")

# Default headers for HTTP requests to prevent Bot detection
DEFAULT_HEADERS = {
    "User-Agent": os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36",
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
