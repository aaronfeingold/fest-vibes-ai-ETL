import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import boto3

from ajf_live_re_wire_ETL.shared.schemas.dto import EventDTO
from ajf_live_re_wire_ETL.shared.utils.configs import s3_configs
from ajf_live_re_wire_ETL.shared.utils.errors import S3Error
from ajf_live_re_wire_ETL.shared.utils.helpers import EventDTOEncoder
from ajf_live_re_wire_ETL.shared.utils.logger import logger
from ajf_live_re_wire_ETL.shared.utils.types import ErrorType


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

            return s3_url

        except Exception as e:
            logger.error(f"Error uploading events to S3: {str(e)}")
            raise S3Error(
                message=f"Error uploading events to S3: {str(e)}",
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
