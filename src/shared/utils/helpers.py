"""
Utility functions for the application.
"""

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Dict, Tuple
from urllib.parse import ParseResult, urlencode, urljoin, urlparse

from shared.schemas.dto import ArtistData, EventData, EventDTO, VenueData
from shared.utils.configs import base_configs
from shared.utils.errors import ScrapingError
from shared.utils.logger import logger
from shared.utils.types import ErrorType, ResponseBody, ResponseType


class EventDTOEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for serializing specific objects into JSON format.

    This encoder handles the following types:
    - EventDTO, VenueData, ArtistData, EventData: Converts these objects
        to dictionaries using `asdict`.
    - datetime: Converts datetime objects to ISO 8601 formatted strings.
    - date: Converts date objects to ISO 8601 formatted strings.

    For other object types, the default JSONEncoder behavior is used.
    """

    def default(self, obj):
        """
        Serialize objects into JSON-compatible formats.

        Args:
            obj (Any): The object to serialize. Supported types include:
                - EventDTO, VenueData, ArtistData, EventData: These will be converted
                  to dictionaries using `asdict`.
                - datetime: This will be converted to an ISO 8601 formatted string.
                - date: This will also be converted to an ISO 8601 formatted string.

        Returns:
            Any: A JSON-compatible representation of the object.

        Raises:
            TypeError: If the object type is not supported and cannot be serialized.
        """
        if isinstance(obj, (EventDTO, VenueData, ArtistData, EventData)):
            return asdict(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def generate_url(
    endpoint: str = base_configs["default_endpoint"],
    params: Dict[str, str] = None,
    base_url: str = base_configs["base_url"],
) -> str:
    """
    Generate a URL with query parameters.

    Args:
        params: Query parameters to include in the URL
        endpoint: Endpoint to append to the base URL
        base_url: Base URL to use

    Returns:
        Complete URL with query parameters
    """
    try:
        # First join the base URL with the endpoint
        url = urljoin(base_url, endpoint)
        # Then add query parameters if they exist
        if params:
            url = f"{url}?{urlencode(params)}"
        logger.info(f"Generated URL: {url}")
        return url
    except (TypeError, Exception) as e:
        raise ScrapingError(
            message=f"Failed to create URL: {e}",
            error_type=ErrorType.GENERAL_ERROR,
            status_code=500,
        )


def prepare_database_url(db_url: str) -> Tuple[str, dict]:
    """
    Prepares the database URL for use by:
    1. Validating the URL exists
    2. Detecting SSL requirements
    3. Converting to async-compatible URL if needed

    Args:
        db_url: The database URL to prepare. Example: "postgresql://user:pass@localhost:5432/mydb"

    Returns:
        Tuple containing:
        - The prepared database URL (e.g. "postgresql+asyncpg://user:pass@localhost:5432/mydb")
        - Dictionary of connection arguments (e.g. {"ssl": True} for AWS/Neon hosts)

    Raises:
        ValueError: If the database URL is not provided

    Examples:
        # Local database:
        #   db_url = "postgresql://user:pass@localhost:5432/mydb"
        #   prepared_url = "postgresql+asyncpg://user:pass@localhost:5432/mydb"
        #   connect_args = {}
        #
        # AWS/Neon database:
        #   db_url = "postgresql://user:pass@aws-host:5432/mydb"
        #   prepared_url = "postgresql+asyncpg://user:pass@aws-host:5432/mydb"
        #   connect_args = {"ssl": True}
    """
    if not db_url:
        raise ValueError("Database URL not found in configuration")

    # Detect SSL requirement
    parsed_url: ParseResult = urlparse(db_url)
    hostname = parsed_url.hostname or ""
    use_ssl = "neon" in hostname or "aws" in hostname

    # Convert to async-compatible URL if needed
    if not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    connect_args = {"ssl": use_ssl} if use_ssl else {}
    return db_url, connect_args


def generate_response(status_code: int, body: ResponseBody) -> ResponseType:
    """
    Generate a standardized API response.

    Args:
        status_code: HTTP status code for the response
        body: Response body content

    Returns:
        Formatted response object
    """
    # Handle ErrorType enum conversion...seems like a hack
    if isinstance(body.get("error", {}).get("type", None), ErrorType):
        body["error"]["type"] = body["error"]["type"].value

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": body,
    }


def generate_date_str() -> str:
    """
    Generate a date string in the configured format.

    Returns:
        Date string in the configured format
    """
    date_param = datetime.now(base_configs["timezone"]).date()
    return date_param.strftime(base_configs["date_format"])


def validate_params(query_string_params: Dict[str, str] = {}) -> Dict[str, str]:
    """
    Validate query string parameters.

    Args:
        query_string_params: Query string parameters to validate

    Returns:
        Validated parameters with defaults applied where needed
    """
    # Validate the date parameter
    date_param = query_string_params.get("date")
    if date_param:
        try:
            datetime.strptime(date_param, base_configs["date_format"]).date()
        except ValueError as e:
            raise ScrapingError(
                message=f"Invalid date format: {e}",
                error_type=ErrorType.VALUE_ERROR,
                status_code=400,
            )
    else:
        date_param = generate_date_str()

    return {**query_string_params, "date": date_param}
