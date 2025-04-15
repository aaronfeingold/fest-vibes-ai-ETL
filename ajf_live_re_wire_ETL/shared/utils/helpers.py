"""
Utility functions for the application.
"""

import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union

import boto3
from urllib.parse import urlencode, urljoin

from ..config import config
from ..errors import S3Error, ErrorType
from ..schemas.dto import EventDTO


logger = logging.getLogger(__name__)


class AwsInfo(TypedDict):
    """
    A TypedDict representing AWS-related information.
    """

    aws_request_id: str
    log_stream_name: str


class SuccessResponseBase(TypedDict):
    """
    A base class for representing a successful response.
    """

    status: str
    data: Any
    date: str


class ErrorResponseBase(TypedDict):
    """
    A TypedDict representing the structure of an error response.
    """

    status: str
    error: Dict[str, str]


# Define the response types
SuccessResponse = Union[SuccessResponseBase, AwsInfo]
ErrorResponse = Union[ErrorResponseBase, AwsInfo]
ResponseBody = Union[SuccessResponse, ErrorResponse]


class ResponseType(TypedDict):
    """
    ResponseType is a TypedDict that defines the structure of a response object.
    """

    statusCode: int
    headers: Dict[str, str]
    body: ResponseBody


class EventDTOEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for serializing specific objects into JSON format.
    """

    def default(self, obj):
        """
        Serialize objects into JSON-compatible formats.
        """
        if isinstance(obj, EventDTO):
            return {
                "artist_data": obj.artist_data,
                "venue_data": obj.venue_data,
                "event_data": obj.event_data,
                "performance_time": obj.performance_time,
                "scrape_time": obj.scrape_time,
            }
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def generate_url(
    params: Dict[str, str] = None,
    endpoint: str = None,
    base_url: str = None,
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
    params = params or {}
    endpoint = endpoint or config.scraper.endpoint
    base_url = base_url or config.scraper.base_url

    # First join the base URL with the endpoint
    url = urljoin(base_url, endpoint)

    # Then add query parameters if they exist
    if params:
        url = f"{url}?{urlencode(params)}"

    return url


def generate_response(status_code: int, body: ResponseBody) -> ResponseType:
    """
    Generate a standardized API response.

    Args:
        status_code: HTTP status code for the response
        body: Response body content

    Returns:
        Formatted response object
    """
    # Handle ErrorType enum conversion
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
    date_param = datetime.now(config.timezone).date()
    return date_param.strftime(config.scraper.date_format)


def validate_params(query_string_params: Dict[str, str] = None) -> Dict[str, str]:
    """
    Validate query string parameters.

    Args:
        query_string_params: Query string parameters to validate

    Returns:
        Validated parameters with defaults applied where needed
    """
    query_string_params = query_string_params or {}

    # Validate the date parameter
    date_param = query_string_params.get("date")
    if date_param:
        try:
            datetime.strptime(date_param, config.scraper.date_format).date()
        except ValueError as e:
            from ..errors import ScrapingError

            raise ScrapingError(
                message=f"Invalid date format: {e}",
                error_type=ErrorType.VALUE_ERROR,
                status_code=400,
            )
    else:
        date_param = generate_date_str()

    return {**query_string_params, "date": date_param}


class S3Helper:
    """Helper class for interacting with S3."""

    def __init__(self):
        self.s3_client = boto3.client("s3", region_name=config.s3.region)
        self.bucket_name = config.s3.bucket_name

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and injection attacks.
        """
        # Remove any path traversal attempts
        filename = filename.replace("../", "").replace("..\\", "")
        # Remove any non-alphanumeric characters except - and _
        filename = re.sub(r"[^a-zA-Z0-9\-_\.]", "", filename)
        return filename

    @staticmethod
    async def cleanup_local_files(filepath: str) -> None:
        """
        Clean up local files after they've been uploaded to S3.
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Successfully cleaned up local file: {filepath}")
        except Exception as e:
            logger.error(f"Error cleaning up local file {filepath}: {str(e)}")

    async def save_events_local(
        self,
        events: List[EventDTO],
        *,
        date_str: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Save events to a local JSON file for development purposes.

        Args:
            events: List of EventDTO objects to save
            date_str: Optional date string to include in filename
            filename: Optional custom filename to use

        Returns:
            Path to the saved file
        """
        # Setup data directory in project root
        data_dir = Path("/tmp/data")
        data_dir.mkdir(exist_ok=True)

        # Generate or use provided filename
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if date_str:
                # Sanitize the date_str before using it in filename
                safe_date = self.sanitize_filename(date_str)
                filename = f"event_data_{safe_date}_{timestamp}.json"
            else:
                filename = f"event_data_{timestamp}.json"
        else:
            # Sanitize any provided filename
            filename = self.sanitize_filename(filename)

        # Ensure .json extension
        if not filename.endswith(".json"):
            filename += ".json"

        # Create full filepath
        filepath = data_dir / filename

        # Save to file
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(events, f, cls=EventDTOEncoder, indent=2, ensure_ascii=False)

        return str(filepath)

    async def upload_to_s3(self, filepath: str, key_prefix: str = "raw_events") -> str:
        """
        Upload a file to S3 bucket.

        Args:
            filepath: Path to the local file to upload
            key_prefix: S3 key prefix for organization

        Returns:
            S3 URL of the uploaded file
        """
        try:
            # Get just the filename from the full path
            filename = Path(filepath).name

            # Create a unique key for S3 using timestamp and filename
            timestamp = datetime.now().strftime("%Y/%m/%d")
            s3_key = f"{key_prefix}/{timestamp}/{filename}"

            logger.info(
                f"Uploading {filepath} to S3 bucket {self.bucket_name} with key {s3_key}"
            )

            # Upload the file
            self.s3_client.upload_file(
                filepath,
                self.bucket_name,
                s3_key,
                ExtraArgs={"ContentType": "application/json"},
            )

            # Generate the S3 URL
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Successfully uploaded file to {s3_url}")

            # Clean up the local file after successful upload
            await self.cleanup_local_files(filepath)

            return s3_url

        except Exception as e:
            logger.error(f"Error uploading file to S3: {str(e)}")
            raise S3Error(
                message=f"Error uploading file to S3: {str(e)}",
                error_type=ErrorType.S3_ERROR,
                status_code=500,
            )

    async def download_from_s3(
        self, s3_key: str, local_path: Optional[str] = None
    ) -> str:
        """
        Download a file from S3 bucket.

        Args:
            s3_key: S3 key of the file to download
            local_path: Optional path to save the downloaded file

        Returns:
            Path to the downloaded file
        """
        try:
            # Generate a local path if not provided
            if local_path is None:
                filename = Path(s3_key).name
                data_dir = Path("/tmp/data")
                data_dir.mkdir(exist_ok=True)
                local_path = str(data_dir / filename)

            logger.info(
                f"Downloading from S3 bucket {self.bucket_name}, key {s3_key} to {local_path}"
            )

            # Download the file
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Successfully downloaded file to {local_path}")

            return local_path

        except Exception as e:
            logger.error(f"Error downloading file from S3: {str(e)}")
            raise S3Error(
                message=f"Error downloading file from S3: {str(e)}",
                error_type=ErrorType.S3_ERROR,
                status_code=500,
            )

    def list_files(self, prefix: str) -> List[str]:
        """
        List files in S3 bucket with a given prefix.

        Args:
            prefix: S3 key prefix to list

        Returns:
            List of S3 keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
            )

            if "Contents" not in response:
                return []

            return [obj["Key"] for obj in response["Contents"]]

        except Exception as e:
            logger.error(f"Error listing files in S3: {str(e)}")
            raise S3Error(
                message=f"Error listing files in S3: {str(e)}",
                error_type=ErrorType.S3_ERROR,
                status_code=500,
            )
