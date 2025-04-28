"""
Test invoker for the date range generator component.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from dotenv import load_dotenv

from ajf_live_re_wire_ETL.date_range_generator.app import generate_date_ranges

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
    start_date: str = None, end_date: str = None, days_ahead: int = 7
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
    if start_date is None:
        start_date = datetime.now().strftime("%Y-%m-%d")

    if end_date is None:
        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    event = {"queryStringParameters": {"start_date": start_date, "end_date": end_date}}

    logger.info(f"Generating date ranges from {start_date} to {end_date}")
    result = await generate_date_ranges(event, LambdaTestContext())
    logger.info(f"Date range result: {json.dumps(result, indent=2)}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test invoker for the date range generator"
    )
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD format)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD format)")
    parser.add_argument(
        "--days-ahead", type=int, default=7, help="Number of days to look ahead"
    )
    args = parser.parse_args()

    asyncio.run(
        invoke_date_range_generator(args.start_date, args.end_date, args.days_ahead)
    )
