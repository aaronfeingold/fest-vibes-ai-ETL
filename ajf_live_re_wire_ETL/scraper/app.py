"""
Main application for the scraper component.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

from shared.config import config
from shared.errors import ScrapingError, ErrorType
from shared.utils.helpers import (
    S3Helper,
    generate_response,
    validate_params,
    EventDTOEncoder,
)

from .service import DeepScraper

logger = logging.getLogger(__name__)


async def scrape_and_store(
    event: Dict[str, Any],
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Scrape event data and store it in S3.

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

    scraper = None
    try:
        # Extract query parameters from the event
        query_params = event.get("queryStringParameters", {})

        # Validate and normalize parameters
        params = validate_params(query_params)
        scrape_time = datetime.now(config.timezone).date()

        logger.info(f"Scraping events for date: {params['date']}")

        # Create and run the scraper
        scraper = DeepScraper()
        events = await scraper.run(params)

        logger.info(f"Scraped {len(events)} events for date: {params['date']}")

        # Save events to a local file
        s3_helper = S3Helper()
        filepath = await s3_helper.save_events_local(
            events=events, date_str=params["date"]
        )
        logger.info(f"Saved event data to file: {filepath}")

        # Upload to S3
        s3_url = await s3_helper.upload_to_s3(filepath)
        logger.info(f"Uploaded event data to S3: {s3_url}")

        # Return success response
        return generate_response(
            200,
            {
                "status": "success",
                "message": f"Successfully scraped and stored events for {params['date']}",
                "date": params["date"],
                "event_count": len(events),
                "s3_url": s3_url,
                **aws_info,
            },
        )

    except ScrapingError as e:
        logger.error(f"Scraping error: {e.error_type.value} - {e.message}")
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
        if scraper:
            await scraper.close()


def lambda_handler(event, context):
    """
    Lambda handler function.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        Response object
    """
    return asyncio.run(scrape_and_store(event, context))


if __name__ == "__main__":
    """Run the scraper as a script for testing."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create a mock event and context
    mock_event = {
        "queryStringParameters": {
            "date": datetime.now(config.timezone).strftime(config.scraper.date_format)
        }
    }
    mock_context = None

    # Run the scraper
    result = asyncio.run(scrape_and_store(mock_event, mock_context))

    # Print the result
    print(json.dumps(result, indent=2))
