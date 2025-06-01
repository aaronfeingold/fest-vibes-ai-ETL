import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse

import pytz
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

from ajf_live_re_wire_ETL.main import DatabaseHandler, lambda_handler

# TODO: DEPRECATE ME

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Debug: Print database URL (with password masked)
db_url = os.getenv("PG_DATABASE_URL", "")
if db_url:
    parsed = urlparse(db_url)
    safe_netloc = f"****:****@{parsed.hostname}"
    if parsed.port:
        safe_netloc += f":{parsed.port}"
    masked_url = urlunparse(parsed._replace(netloc=safe_netloc))
    logger.info(f"Database URL found: {masked_url}")
else:
    logger.error("No database URL found in environment variables!")


# Simulated AWS Lambda context
class LambdaTestContext:
    aws_request_id = "test-request-id"
    log_stream_name = "test-log-stream"
    function_name = "test-function"
    function_version = "1.0"
    memory_limit_in_mb = 128
    invoked_function_arn = (
        "arn:aws:lambda:us-west-2:123456789012:function:test-function"
    )
    remaining_time_in_millis = 30000  # Simulated remaining time


async def scrape_for_date(date_str: str):
    """Scrape events for a specific date."""
    event = {
        "queryStringParameters": {"date": date_str},
        "httpMethod": "POST",
        "devEnv": False,
    }

    logger.info(f"Scraping for date: {date_str}")
    result = await lambda_handler(event, LambdaTestContext())
    logger.info(f"Scrape result for {date_str}: {json.dumps(result, indent=2)}")
    return result


async def scrape_next_week():
    """Scrape events for today and the next 7 days."""
    today = datetime.now(pytz.timezone("America/Chicago")).date()

    for days_ahead in range(8):  # Today + 7 days
        target_date = today + timedelta(days=days_ahead)
        date_str = target_date.strftime("%Y-%m-%d")
        await scrape_for_date(date_str)

        # Add a small delay between requests to avoid overwhelming the server
        if days_ahead < 7:  # Don't delay after the last request
            await asyncio.sleep(1)


async def check_database():
    """Check if events were saved to the database."""
    db = None
    try:
        logger.info("Creating database handler...")
        db = await DatabaseHandler.create()
        logger.info("Database handler created successfully")

        async with db.get_session():
            logger.info("Checking for events with embeddings...")
            try:
                embeddings = await db.inspect_embeddings(limit=5)
                if embeddings:
                    logger.info("Found events with embeddings:")
                    for event in embeddings:
                        logger.info(
                            (
                                f"Event ID: {event['id']}, Artist: {event['artist']}, "
                                f"Venue: {event['venue']}"
                            )
                        )
                else:
                    logger.warning("No events with embeddings found in database")
            except SQLAlchemyError as e:
                logger.error(f"Database error while checking embeddings: {str(e)}")
                logger.error(traceback.format_exc())
                raise
    except Exception as e:
        logger.error(f"Error in check_database: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    finally:
        if db:
            logger.info("Closing database connection...")
            await db.close()
            logger.info("Database connection closed")


# Invoke the handler and print the result
async def test_lambda_handler():
    try:
        logger.info("Starting lambda handler test...")

        # Scrape for today and the next 7 days
        await scrape_next_week()

        # Check the database after saving
        logger.info("Checking database for saved events...")
        await check_database()
        logger.info("Database check completed")
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    asyncio.run(test_lambda_handler())
