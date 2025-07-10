"""
Shared library for AJF Live Re-wire ETL project.
"""

from .cache import redis_cache
from .db import db, models
from .schemas import ArtistData, EventData, EventDTO, VenueData
from .services import GeocodingService, geocoding_service
from .utils import (
    DatabaseError,
    ErrorType,
    EventDTOEncoder,
    RedisError,
    S3Error,
    ScrapingError,
    base_configs,
    generate_date_str,
    generate_response,
    generate_url,
    logger,
    validate_params,
)

__version__ = "0.1.0"
