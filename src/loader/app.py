"""
Main application for the database component.
- Responsible for retrieving the DTO JSON list from S3
- Transforms the DTOs into the database models
  - Generates embeddings for the events
- Loads the data into the database
"""

import asyncio
import json
from typing import Any, Dict

from shared.schemas.dto import ArtistData, EventData, EventDTO, VenueData
from shared.services.s3_service import S3Service
from shared.utils.errors import DatabaseError, ErrorType, S3Error
from shared.utils.helpers import generate_response
from shared.utils.logger import logger

from .service import DatabaseService


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
            s3_records = [{"s3": s3_key}]

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
    mock_event = {"s3_key": "raw_events/2025/04/14/event_data_20250414_120000.json"}
    mock_context = None

    # Run the loader
    result = asyncio.run(app(mock_event, mock_context))

    # Print the result
    print(json.dumps(result, indent=2))
