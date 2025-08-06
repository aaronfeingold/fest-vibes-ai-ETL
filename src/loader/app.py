"""
Main application for the database component.
- Responsible for retrieving the DTO JSON list from S3
- Transforms the DTOs into the database models
  - Generates embeddings for the events
- Loads the data into the database
"""

import asyncio
import json
import re
from typing import Any, Dict

from shared.schemas.dto import ArtistData, EventData, EventDTO, VenueData
from shared.services.s3_service import S3Service
from shared.utils.errors import DatabaseError, ErrorType, S3Error
from shared.utils.helpers import generate_response
from shared.utils.logger import logger

from .service import DatabaseService


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


async def app(
    event: Dict[str, Any],
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Load event data from S3 and store it in the database.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Response object with database operation summary
    """
    # Record the AWS request ID and log stream name if available
    aws_info = {}
    if context and hasattr(context, "aws_request_id"):
        aws_info = {
            "aws_request_id": context.aws_request_id,
            "log_stream_name": context.log_stream_name,
        }

    db_loader = None
    try:
        s3_key = event.get("s3_key")
        if not s3_key:
            raise S3Error(
                message="No S3 records or key provided in the event",
                error_type=ErrorType.S3_ERROR,
                status_code=400,
            )
        s3_records = [{"s3": s3_key}]

        date = event.get("date")
        if not date:
            logger.warning(
                "No date provided in the event, attempting to extract from S3 key"
            )
            date = extract_date_from_s3_key(s3_key)
            if not date:
                raise Exception(
                    message="No date provided in event and could not extract date from S3 key",
                    status_code=400,
                )
            logger.info(f"Successfully extracted date '{date}' from S3 key: {s3_key}")

        # Initialize services
        s3 = S3Service()
        db_loader = DatabaseService()
        await db_loader.initialize()

        # Track database operation results
        operation_summary = {
            "files_processed": len(s3_records),
            "artists_created": 0,
            "artists_created": 0,
            "venues_created": 0,
            "genres_created": 0,
            "events_created": 0,
        }

        # Process each S3 record
        for record in s3_records:
            s3_key = record["s3"]
            logger.info(f"Processing S3 object: {s3_key}")

            # Read and parse JSON directly from S3
            events_data = await s3.read_json_from_s3(s3_key)

            # Convert to EventDTO objects
            events = [
                EventDTO(
                    artist_data=ArtistData(**event_data["artist_data"]),
                    venue_data=VenueData(**event_data["venue_data"]),
                    event_data=EventData(**event_data["event_data"]),
                    performance_time=event_data["performance_time"],
                    scrape_time=event_data["scrape_time"],
                )
                for event_data in events_data
            ]

            logger.info(f"Loaded {len(events)} events from S3")

            # TRANSFORM and LOAD events to the database
            db_results = await db_loader.save_events(events)

            # Update operation summary with database results
            operation_summary.update(db_results)

        # Return success response with operation summary
        return generate_response(
            200,
            {
                "status": "success",
                "message": "Successfully loaded events into the database",
                "operation_summary": operation_summary,
                "s3_key": s3_key,
                "date": date,
                **aws_info,
            },
        )

    except (S3Error, DatabaseError) as e:
        logger.error(f"{e.error_type.value} error: {e.message}")
        return generate_response(
            e.status_code,
            {
                "status": "error",
                "error": {
                    "type": e.error_type,
                    "message": e.message,
                },
                **aws_info,
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return generate_response(
            500,
            {
                "status": "error",
                "error": {
                    "type": ErrorType.UNKNOWN_ERROR,
                    "message": f"An unexpected error occurred: {e}",
                },
                **aws_info,
            },
        )
    finally:
        # Clean up resources
        if db_loader:
            await db_loader.close()


def lambda_handler(event, context):
    """
    Lambda handler function.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Response object
    """
    return asyncio.run(app(event, context))


if __name__ == "__main__":
    """Run the loader as a script for testing."""
    import os

    s3_key = os.getenv(
        "TEST_S3_KEY", "raw_events/2025/04/14/event_data_20250414_120000.json"
    )

    mock_event = {"s3_key": s3_key}
    mock_context = None

    try:
        logger.info("Starting loader execution...")

        # Ensure we're calling the async function properly
        coro = app(mock_event, mock_context)
        logger.info(f"Created coroutine: {type(coro)}")

        # Run the async function
        result = asyncio.run(coro)

        logger.info("Loader execution completed successfully")

        # Print the result
        print(json.dumps(result, indent=2))

    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
