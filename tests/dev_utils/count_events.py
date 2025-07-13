import asyncio
import logging

from sqlalchemy import text

from src.main import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def count_events():
    """Count events in the database."""
    try:
        logger.info("Creating database handler...")
        db = await DatabaseHandler.create()

        logger.info("Counting events...")
        async with db.get_session() as session:
            # Count total events
            result = await session.execute(text("SELECT COUNT(*) FROM events"))
            total_events = result.scalar()

            # Count events with embeddings
            result = await session.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM events
                WHERE description_embedding IS NOT NULL
                OR event_text_embedding IS NOT NULL
            """
                )
            )
            events_with_embeddings = result.scalar()

            logger.info(f"Total events in database: {total_events}")
            logger.info(f"Events with embeddings: {events_with_embeddings}")

        await db.close()

    except Exception as e:
        logger.error(f"Error counting events: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(count_events())
