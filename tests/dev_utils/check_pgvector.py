import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

from ETL.main import DatabaseHandler

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_pgvector():
    db = await DatabaseHandler.create()
    try:
        async with db.get_session() as session:
            # Check if pgvector extension exists
            result = await session.execute(
                text("SELECT * FROM pg_extension WHERE extname = 'vector'")
            )
            extension = result.fetchone()

            if extension:
                logger.info("pgvector extension is installed!")

                # Check if any tables exist
                result = await session.execute(
                    text(
                        """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """
                    )
                )
                tables = result.fetchall()
                logger.info("Database tables:")
                for table in tables:
                    logger.info(f"- {table[0]}")
            else:
                logger.error("pgvector extension is NOT installed!")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_pgvector())
