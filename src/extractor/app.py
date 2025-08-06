"""
Main application for the scraper component.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from shared.services.s3_service import S3Service
from shared.utils.configs import base_configs
from shared.utils.errors import ScrapingError
from shared.utils.helpers import generate_response, validate_params
from shared.utils.logger import logger
from shared.utils.types import ErrorType

from .service import ScraperService


async def app(
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
    aws_info = {}
    if context and hasattr(context, "aws_request_id"):
        aws_info = {
            "aws_request_id": context.aws_request_id,
            "log_stream_name": context.log_stream_name,
        }

    scraper = None
    try:
        query_params = event.get("queryStringParameters", {})

        params = validate_params(query_params)

        scraper = ScraperService()
        events = await scraper.run(params)

        s3 = S3Service()
        s3_url, s3_key = await s3.upload_events_to_s3(
            events=events, scrape_date_str=params["date"]
        )
        logger.info(f"Uploaded event data to S3: {s3_url}")

        return generate_response(
            200,
            {
                "status": "success",
                "message": f"Successfully scraped and stored events for {params['date']}",
                "date": params["date"],
                "event_count": len(events),
                "s3_url": s3_url,
                "s3_key": s3_key,
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
    return asyncio.run(app(event, context))


if __name__ == "__main__":
    """Run the scraper as a script for testing."""
    mock_event = {
        "queryStringParameters": {
            "date": datetime.now(base_configs["timezone"]).strftime(
                base_configs["date_format"]
            )
        }
    }
    mock_context = None

    result = asyncio.run(app(mock_event, mock_context))

    print(json.dumps(result, indent=2))
