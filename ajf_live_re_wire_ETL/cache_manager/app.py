"""
Main application for the cache manager component.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from shared.config import config
from shared.errors import DatabaseError, ErrorType, RedisError
from shared.utils.helpers import generate_response

from .service import CacheManager

logger = logging.getLogger(__name__)


async def update_cache(
    event: Dict[str, Any],
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Update Redis cache with event data from the database.

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

    cache_manager = None
    try:
        # Extract parameters from the event
        date_str = event.get("date")
        start_date = event.get("start_date")
        end_date = event.get("end_date")

        # Initialize the cache manager
        cache_manager = CacheManager()
        await cache_manager.initialize()

        # Determine which operation to perform
        if date_str:
            # Update cache for a single date
            logger.info(f"Updating cache for date: {date_str}")
            event_count = await cache_manager.update_cache_for_date(date_str)

            return generate_response(
                200,
                {
                    "status": "success",
                    "message": f"Successfully updated cache for date {date_str}",
                    "date": date_str,
                    "event_count": event_count,
                    **aws_info,
                },
            )

        elif start_date and end_date:
            # Update cache for a date range
            logger.info(f"Updating cache for date range: {start_date} to {end_date}")
            results = await cache_manager.update_cache_for_date_range(
                start_date, end_date
            )

            # Check if any updates failed
            failures = {date: count for date, count in results.items() if count == -1}

            if failures:
                return generate_response(
                    207,  # Partial success
                    {
                        "status": "partial_success",
                        "message": f"Cache update completed with {len(failures)} failures",
                        "results": results,
                        "failures": list(failures.keys()),
                        **aws_info,
                    },
                )
            else:
                return generate_response(
                    200,
                    {
                        "status": "success",
                        "message": "Successfully updated cache for all dates in range",
                        "results": results,
                        **aws_info,
                    },
                )
        else:
            # Default to today's date if no parameters provided
            today = datetime.now(config.timezone).strftime("%Y-%m-%d")
            logger.info(f"No date parameters provided, using today's date: {today}")
            event_count = await cache_manager.update_cache_for_date(today)

            return generate_response(
                200,
                {
                    "status": "success",
                    "message": f"Successfully updated cache for today ({today})",
                    "date": today,
                    "event_count": event_count,
                    **aws_info,
                },
            )

    except (DatabaseError, RedisError) as e:
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
        if cache_manager:
            await cache_manager.close()


def lambda_handler(event, context):
    """
    Lambda handler function.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Response object
    """
    return asyncio.run(update_cache(event, context))


if __name__ == "__main__":
    """Run the cache manager as a script for testing."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create a mock event
    today = datetime.now(config.timezone).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(config.timezone) + timedelta(days=1)).strftime("%Y-%m-%d")

    mock_event = {
        # "date": today,  # Uncomment to update a single date
        "start_date": today,
        "end_date": tomorrow,
    }
    mock_context = None

    # Run the cache manager
    result = asyncio.run(update_cache(mock_event, mock_context))

    # Print the result
    print(json.dumps(result, indent=2))
