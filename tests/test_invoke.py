import json
import asyncio
import logging
import os
import traceback
from datetime import datetime
import pytz
from main import lambda_handler, DatabaseHandler, Utilities
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

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
    masked_url = db_url.replace("://", "://***:***@")
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


# Simulated event data with today's date
event = {
    "queryStringParameters": {"date": Utilities.generate_date_str()},
    "httpMethod": "POST",
    "devEnv": False,
}


async def check_database():
    """Check if events were saved to the database"""
    db = None
    try:
        logger.info("Creating database handler...")
        db = await DatabaseHandler.create()
        logger.info("Database handler created successfully")

        async with db.get_session() as session:
            logger.info("Checking for events with embeddings...")
            try:
                embeddings = await db.inspect_embeddings(limit=5)
                if embeddings:
                    logger.info("Found events with embeddings:")
                    for event in embeddings:
                        logger.info(
                            f"Event ID: {event['id']}, Artist: {event['artist']}, Venue: {event['venue']}"
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
        result = await lambda_handler(event, LambdaTestContext())
        print(json.dumps(result, indent=4))

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
