"""
Test invoker for the scraper component.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv

from ajf_live_re_wire_ETL.extract.app import scrape_and_store
from ajf_live_re_wire_ETL.shared.utils.logger import logger

# Load environment variables
load_dotenv()


class LambdaTestContext:
    """Mock Lambda context for testing."""

    aws_request_id = "test-request-id"
    log_stream_name = "test-log-stream"
    function_name = "test-scraper"
    function_version = "1.0"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-west-2:123456789012:function:test-scraper"
    remaining_time_in_millis = 30000


async def invoke(date_str: str = None) -> Dict[str, Any]:
    """
    Invoke the scraper for a specific date.

    Args:
        date_str: Date string in YYYY-MM-DD format. If None, uses today's date.

    Returns:
        The scraper's response
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")  # set a default date to now

    event = {"queryStringParameters": {"date": date_str}}

    logger.info(f"Invoking scraper for date: {date_str}")
    result = await scrape_and_store(event, LambdaTestContext())
    logger.info(f"Scraper result: {json.dumps(result, indent=2)}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test invoker for the scraper component"
    )
    parser.add_argument("--date", type=str, help="Date to scrape (YYYY-MM-DD format)")
    args = parser.parse_args()

    asyncio.run(invoke(args.date))
