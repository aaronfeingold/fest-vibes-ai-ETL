"""
Test invoker for the scraper component.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv

from shared.utils.logger import logger
from src.extractor.app import app

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


async def invoke(date_str: str = datetime.now().strftime("%Y-%m-%d")) -> Dict[str, Any]:
    """
    Invoke the scraper for a specific date.

    Args:
        date_str: Date string in YYYY-MM-DD format. If None, uses today's date.

    Returns:
        The scraper's response
    """
    event = {"queryStringParameters": {"date": date_str}}

    logger.info(f"Invoking scraper for date: {date_str}")
    result = await app(event, LambdaTestContext())
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
