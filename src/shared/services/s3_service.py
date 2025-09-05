import json
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from shared.schemas.dto import EventDTO
from shared.utils.configs import s3_configs
from shared.utils.errors import ErrorType, S3Error
from shared.utils.helpers import EventDTOEncoder
from shared.utils.logger import logger


class S3Service:
    """Helper class for interacting with S3."""

    def __init__(self):
        self.s3_client = boto3.client("s3", region_name=s3_configs["s3_region"])
        self.bucket_name = s3_configs["s3_bucket_name"]

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and injection attacks.
        """
        filename = filename.replace("../", "").replace("..\\", "")
        filename = re.sub(r"[^a-zA-Z0-9\-_\.]", "", filename)
        return filename

    @staticmethod
    def extract_date_from_s3_key(s3_key: str) -> str | None:
        """
        Extract date from S3 key format like:
        raw_events/2025/07/30/event_data_2025-07-29_20250730_002901.json

        Returns date in the app-wide format (YYYY-MM-DD) or None if not found.
        """
        try:
            # Method 1: Extract from path structure (raw_events/YYYY/MM/DD/)
            path_match = re.search(r"raw_events/(\d{4})/(\d{2})/(\d{2})/", s3_key)
            if path_match:
                year, month, day = path_match.groups()
                return f"{year}-{month}-{day}"

            # Method 2: Extract from filename (event_data_YYYY-MM-DD_)
            filename_match = re.search(r"event_data_(\d{4}-\d{2}-\d{2})_", s3_key)
            if filename_match:
                return filename_match.group(1)

            # Method 3: Extract YYYYMMDD format and convert
            yyyymmdd_match = re.search(r"_(\d{8})_", s3_key)
            if yyyymmdd_match:
                date_str = yyyymmdd_match.group(1)
                year = date_str[:4]
                month = date_str[4:6]
                day = date_str[6:8]
                return f"{year}-{month}-{day}"

            return None
        except Exception as e:
            logger.warning(f"Failed to extract date from S3 key '{s3_key}': {e}")
            return None

    async def upload_events_to_s3(
        self,
        events: List[EventDTO],
        *,
        scrape_date_str: Optional[str] = None,
        key_prefix: str = "raw_events",
    ) -> str:
        """
        Upload events directly to S3 without saving to local filesystem first.

        Args:
            events: List of EventDTO objects to upload
            scrape_date_str: String representing the date for which events were scraped
            key_prefix: S3 key prefix for organization

        Returns:
            S3 URL of the uploaded file
        """
        try:
            # Generate filename using both scrape date and current timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            date_component = f"_{scrape_date_str}" if scrape_date_str else ""
            filename = f"event_data{date_component}_{timestamp}.json"

            # Create a timestamp-based path for S3 key
            date_path = datetime.now().strftime("%Y/%m/%d")
            s3_key = f"{key_prefix}/{date_path}/{filename}"

            # Serialize the data to JSON
            json_data = json.dumps(
                events, cls=EventDTOEncoder, indent=2, ensure_ascii=False
            )

            # Create a BytesIO buffer
            buffer = BytesIO(json_data.encode("utf-8"))

            logger.info(
                f"Uploading events directly to S3 bucket {self.bucket_name} with key {s3_key}"
            )

            # Upload the buffer to S3
            self.s3_client.upload_fileobj(
                buffer,
                self.bucket_name,
                s3_key,
                ExtraArgs={"ContentType": "application/json"},
            )

            # Generate the S3 URL
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Successfully uploaded events to {s3_url}")

            return s3_url, s3_key

        except Exception as e:
            logger.error(f"Error uploading events to S3: {str(e)}")
            raise S3Error(
                message=f"Error uploading events to S3: {str(e)}",
                error_type=ErrorType.S3_ERROR,
                status_code=500,
            )

    async def read_json_from_s3(self, s3_key: str) -> List[Dict[str, Any]]:
        """
        Read and parse JSON data directly from S3 without saving to disk.

        Args:
            s3_key: The S3 key to read from

        Returns:
            Parsed JSON data as a list of dictionaries

        Raises:
            S3Error: If there's an error reading from S3 or parsing the JSON
        """
        try:
            logger.info(f"Reading JSON from S3: {s3_key}")
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            json_data = json.loads(response["Body"].read().decode("utf-8"))
            logger.info(f"Successfully read and parsed JSON from {s3_key}")
            return json_data
        except ClientError as e:
            error_message = f"Error reading from S3: {str(e)}"
            logger.error(error_message)
            raise S3Error(
                message=error_message,
                error_type=ErrorType.S3_ERROR,
                status_code=500,
            )
        except json.JSONDecodeError as e:
            error_message = f"Error parsing JSON from S3: {str(e)}"
            logger.error(error_message)
            raise S3Error(
                message=error_message,
                error_type=ErrorType.S3_ERROR,
                status_code=500,
            )
