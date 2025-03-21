import asyncio
import logging
from sqlalchemy import text
from main import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def clear_tables():
    """Clear all tables in the database"""
    try:
        logger.info("Creating database handler...")
        db = await DatabaseHandler.create()

        logger.info("Clearing all tables...")
        async with db.get_session() as session:
            # Read the SQL file
            with open('tests/clear_tables.sql', 'r') as file:
                sql_commands = file.read()

            # Execute each command
            for command in sql_commands.split(';'):
                if command.strip():
                    await session.execute(text(command))

            await session.commit()
            logger.info("Successfully cleared all tables")

        await db.close()

    except Exception as e:
        logger.error(f"Error clearing tables: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(clear_tables())
