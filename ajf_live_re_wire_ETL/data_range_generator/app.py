"""
Date range generator component.

This Lambda function generates a range of dates from today to a specified
number of days in the future, which can be used to trigger the scraper
component for each date in the range.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from shared.config import config
from shared.errors import ErrorType
from shared.utils.helpers import generate_response

logger = logging.getLogger(__name__)


def generate_date_range(days_ahead: int = 30) -> List[str]:
    """
    Generate a range of dates from today to N days ahead.

    Args:
        days_ahead: Number of days to include in the range

    Returns:
        List of date strings in YYYY-MM-DD format
    """
    today = datetime.now(config.timezone).date()
    date_range = [
        (today + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days_ahead + 1)  # Include today (i=0) and days_ahead
    ]
    return date_range


def lambda_handler(event, context):
    """
    Lambda handler function.

    Args:
        event: Lambda event object containing optional 'days_ahead' parameter
        context: Lambda context object

    Returns:
        Response object with the generated date range
    """
    # Record the AWS request ID and log stream name if available
    aws_info = {}
    if context and hasattr(context, "aws_request_id"):
        aws_info = {
            "aws_request_id": context.aws_request_id,
            "log_stream_name": context.log_stream_name,
        }

    try:
        # Extract parameters from the event
        days_ahead = int(event.get("days_ahead", 30))

        # Validate input
        if days_ahead < 0:
            return generate_response(
                400,
                {
                    "status": "error",
                    "error": {
                        "type": ErrorType.VALUE_ERROR.value,
                        "message": "days_ahead must be a non-negative integer",
                    },
                    **aws_info,
                },
            )

        # Generate the date range
        date_range = generate_date_range(days_ahead)

        # Return the date range
        return {
            "dates": date_range,
            "start_date": date_range[0],
            "end_date": date_range[-1],
            "count": len(date_range),
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return generate_response(
            500,
            {
                "status": "error",
                "error": {
                    "type": ErrorType.UNKNOWN_ERROR.value,
                    "message": f"An unexpected error occurred: {e}",
                },
                **aws_info,
            },
        )


if __name__ == "__main__":
    """Run the date range generator as a script for testing."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create a mock event
    mock_event = {
        "days_ahead": 7,  # Generate dates for the next week
    }
    mock_context = None

    # Run the date range generator
    result = lambda_handler(mock_event, mock_context)

    # Print the result
    print(json.dumps(result, indent=2))
