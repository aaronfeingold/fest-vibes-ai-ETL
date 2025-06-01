"""
Test invoker for the cache manager component.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from dotenv import load_dotenv

from ajf_live_re_wire_ETL.cache_manager.app import app

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
    function_name = "test-cache-manager"
    function_version = "1.0"
    memory_limit_in_mb = 128
    invoked_function_arn = (
        "arn:aws:lambda:us-west-2:123456789012:function:test-cache-manager"
    )
    remaining_time_in_millis = 30000


async def invoke_cache_manager(date_str: str) -> Dict[str, Any]:
    """
    Invoke the cache manager for a specific date.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        The cache manager's response
    """
    event = {"queryStringParameters": {"date": date_str}}

    logger.info(f"Invoking cache manager for date: {date_str}")
    result = await app(event, LambdaTestContext())
    logger.info(f"Cache manager result: {json.dumps(result, indent=2)}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test invoker for the cache manager")
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="Date to manage cache for (YYYY-MM-DD format)",
    )
    args = parser.parse_args()

    asyncio.run(invoke_cache_manager(args.date))
