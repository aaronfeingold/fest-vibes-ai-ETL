"""
Configuration settings for the application.
"""

import os
from typing import Dict, TypedDict

import pytz


class Coordinates(TypedDict):
    latitude: float
    longitude: float


class BaseConfig(TypedDict):
    """Type definition for base configuration values.

    Attributes:
        timezone: pytz timezone object for the application
        default_coords: Default coordinates for location-based operations
        date_format: Format string for date parsing/formatting
        base_url: Base URL for the application
        default_endpoint: Default API endpoint path
        default_headers: Default HTTP headers for requests
    """

    timezone: pytz.BaseTzInfo
    default_coords: Coordinates
    date_format: str
    base_url: str
    default_endpoint: str
    default_headers: Dict[str, str]


base_configs: BaseConfig = {
    "timezone": pytz.timezone("America/Chicago"),
    "default_coords": {
        "latitude": 29.9511,
        "longitude": -90.0715,
    },
    "date_format": "%Y-%m-%d",
    "base_url": os.environ.get("BASE_URL", "https://www.wwoz.org"),
    "default_endpoint": "/calendar/livewire-music",
    "default_headers": {
        "User-Agent": os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36",
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    },
}

db_configs = {
    "pg_database_url": os.getenv("PG_DATABASE_URL"),
    "echo": os.getenv("DB_ECHO", "false").lower()
    == "true",  # Set to True for debugging
    "pool_size": int(os.getenv("DB_POOL_SIZE", 5)),
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 10)),
    "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", 30)),
}

s3_configs = {
    "s3_bucket_name": os.getenv("S3_BUCKET_NAME", "ajf-live-re-wire-data"),
    "s3_region": os.getenv("S3_REGION", "us-east-1"),
}

redis_config = {
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
    "redis_socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", 5)),
    "redis_socket_connect_timeout": int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", 5)),
    "redis_retry_on_timeout": os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower()
    == "true",
    "redis_decode_responses": os.getenv("REDIS_DECODE_RESPONSES", "true").lower()
    == "true",
}
