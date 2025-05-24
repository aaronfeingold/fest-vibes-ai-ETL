"""
Main application for the database loader component.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from ajf_live_re_wire_ETL.shared.schemas.dto import EventDTO
from ajf_live_re_wire_ETL.shared.services.s3_service import S3Service
from ajf_live_re_wire_ETL.shared.utils.configs import base_configs
from ajf_live_re_wire_ETL.shared.utils.errors import DatabaseError, ErrorType, S3Error
from ajf_live_re_wire_ETL.shared.utils.helpers import generate_response
from ajf_live_re_wire_ETL.shared.utils.logger import logger

from .service import DatabaseLoader


async def load_from_s3(
    event: Dict[str, Any],
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Load event data from S3 and store it in the database.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Response object
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
        # Extract S3 event details
        s3_records = event.get("Records", [])
        if not s3_records:
            # Check for direct invocation with S3 key
            s3_key = event.get("s3_key")
            if not s3_key:
                raise S3Error(
                    message="No S3 records or key provided in the event",
                    error_type=ErrorType.S3_ERROR,
                    status_code=400,
                )
            s3_records = [{"s3": {"object": {"key": s3_key}}}]

        # Process each S3 record
        for record in s3_records:
            s3_key = record["s3"]["object"]["key"]
            logger.info(f"Processing S3 object: {s3_key}")

            # Download the file from S3
            s3 = S3Service()
            local_path = await s3.download_from_s3(s3_key)

            # Parse the JSON content
            with open(local_path, "r") as f:
                events_data = json.load(f)

            # Convert to EventDTO objects
            events = []
            for event_data in events_data:
                events.append(EventDTO(**event_data))

            logger.info(f"Loaded {len(events)} events from S3")

            # Initialize the database loader
            db_loader = DatabaseLoader()
            await db_loader.initialize()

            # Save events to the database
            scrape_time = datetime.now(base_configs["timezone"]).date()
            await db_loader.save_events(events, scrape_time)

            # Clean up the local file
            await s3.cleanup_local_files(local_path)

        # Return success response
        return generate_response(
            200,
            {
                "status": "success",
                "message": "Successfully loaded events into the database",
                "record_count": len(s3_records),
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
    return asyncio.run(load_from_s3(event, context))


if __name__ == "__main__":
    """Run the loader as a script for testing."""
    mock_event = {"s3_key": "raw_events/2025/04/14/event_data_20250414_120000.json"}
    mock_context = None

    # Run the loader
    result = asyncio.run(load_from_s3(mock_event, mock_context))

    # Print the result
    print(json.dumps(result, indent=2))
