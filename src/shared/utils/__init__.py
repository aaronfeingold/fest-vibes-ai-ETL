"""
Utility functions and shared resources.
"""

from .configs import base_configs
from .errors import DatabaseError, RedisError, S3Error, ScrapingError
from .helpers import (
    EventDTOEncoder,
    generate_date_str,
    generate_response,
    generate_url,
    validate_params,
)
from .logger import logger
from .types import ErrorType
