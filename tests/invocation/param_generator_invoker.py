"""
Test invoker for the date range generator component.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from dotenv import load_dotenv

from src.param_generator.app import generate_date_range

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class LambdaTestContext:
    """Mock Lambda context for testing."""

    aws_request_id = "test-request-id"
    log_stream_name = "test-log-stream"
    function_name = "test-date-range-generator"
    function_version = "1.0"
    memory_limit_in_mb = 128
    invoked_function_arn = (
        "arn:aws:lambda:us-west-2:123456789012:function:test-date-range-generator"
    )
    remaining_time_in_millis = 30000


async def invoke_date_range_generator(
    start_date: str = None, days_ahead: int = 7
) -> Dict[str, Any]:
    """
    Invoke the date range generator.

    Args:
        start_date: Start date in YYYY-MM-DD format. If None, uses today.
        end_date: End date in YYYY-MM-DD format. If None, uses start_date + days_ahead.
        days_ahead: Number of days to look ahead if end_date is not provided.

    Returns:
        The date range generator's response
    """
    event = {
        "queryStringParameters": {"start_date": start_date, "days_ahead": days_ahead}
    }

    result = await generate_date_range(event, LambdaTestContext())
    logger.info(f"Date range result: {json.dumps(result, indent=2)}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test invoker for the date range generator"
    )
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD format)")
    parser.add_argument(
        "--days-ahead", type=int, default=7, help="Number of days to look ahead"
    )
    args = parser.parse_args()

    asyncio.run(invoke_date_range_generator(args.start_date, args.days_ahead))
