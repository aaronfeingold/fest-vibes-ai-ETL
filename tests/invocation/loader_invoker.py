"""
Test invoker for the loader component.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from dotenv import load_dotenv

from ajf_live_re_wire_ETL.loader.app import process_s3_files

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
    function_name = "test-loader"
    function_version = "1.0"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-west-2:123456789012:function:test-loader"
    remaining_time_in_millis = 30000


async def invoke_loader(date_str: str) -> Dict[str, Any]:
    """
    Invoke the loader for a specific date.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        The loader's response
    """
    event = {"queryStringParameters": {"date": date_str}}

    logger.info(f"Invoking loader for date: {date_str}")
    result = await process_s3_files(event, LambdaTestContext())
    logger.info(f"Loader result: {json.dumps(result, indent=2)}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test invoker for the loader component"
    )
    parser.add_argument(
        "--date", type=str, required=True, help="Date to process (YYYY-MM-DD format)"
    )
    args = parser.parse_args()

    asyncio.run(invoke_loader(args.date))
