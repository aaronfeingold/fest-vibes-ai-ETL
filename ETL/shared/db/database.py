"""
Database utility for connecting to and interacting with the database.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ETL.shared.db.models import Base
from ETL.shared.utils.configs import db_configs
from ETL.shared.utils.errors import DatabaseError, ErrorType
from ETL.shared.utils.helpers import prepare_database_url
from ETL.shared.utils.logger import logger


class Database:
    """Database is a service class.

    Responsible for managing database interactions,
    including creating tables, handling sessionsIt integrates with SQLAlchemy for asynchronous database operations
    and uses a SentenceTransformer model for embedding generation.

    Attributes:
        engine (AsyncEngine): The SQLAlchemy asynchronous engine for database connections.
        async_session (async_sessionmaker): The session maker for creating asynchronous sessions.

    Methods:
        initialize(cls):
            Class method to initialize the DatabaseHandler instance with a database engine
            and session maker. Also ensures tables are created.

        create_tables():
            Asynchronously creates database tables if they do not already exist.

        session():
            Asynchronous context manager for handling database sessions.

        close():
            Cleans up resources by properly disposing of the database engine.
    """

    def __init__(self):
        """
        Initializes the class with the provided database engine, asynchronous session,
        and sets up the embedding model.

        Args:
            engine: The database engine to be used for database operations.
            async_session: The asynchronous session factory for managing database sessions.
        """
        self.db_url, self.connect_args = prepare_database_url(
            db_configs["pg_database_url"]
        )

    async def initialize(self):
        """Initialize the database engine and session maker."""
        try:
            self.engine = create_async_engine(
                self.db_url,
                echo=db_configs["echo"],
                pool_size=db_configs["pool_size"],
                max_overflow=db_configs["max_overflow"],
                pool_timeout=db_configs["pool_timeout"],
                connect_args=self.connect_args,
            )

            # Force metadata refresh
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.reflect)
                await conn.run_sync(Base.metadata.create_all)

            self.async_session = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

            logger.info("Successfully initialized database connection")
            return self

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise DatabaseError(
                message=f"Failed to initialize database: {str(e)}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

    async def create_tables(self):
        """Create database tables if they don't exist."""
        try:
            async with self.engine.begin() as conn:
                # Enable pgvector extension
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

                # Check if tables exist
                result = await conn.execute(
                    text(
                        """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'events'
                    )
                """
                    )
                )
                tables_exist = result.scalar()

                if not tables_exist:
                    logger.info("Tables don't exist, creating them...")
                    await conn.run_sync(Base.metadata.create_all)
                    logger.info("Tables created successfully")
                else:
                    logger.info("Tables already exist, skipping creation")

        except Exception as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise DatabaseError(
                message=f"Failed to create tables: {str(e)}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for database sessions."""
        if not self.async_session:
            await self.initialize()

        session = self.async_session()
        try:
            logger.debug("Starting new database session")
            yield session
            logger.debug("Session yielded, attempting to commit")
            await session.commit()
            logger.debug("Session committed successfully")
        except Exception as e:
            logger.error(f"Error in database session: {str(e)}")
            await session.rollback()
            logger.error("Session rolled back due to error")
            raise DatabaseError(
                message=f"Database session error: {str(e)}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )
        finally:
            logger.debug("Closing database session")
            await session.close()
            logger.debug("Database session closed")

    async def close(self):
        """Close the database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")


# Create a global database instance
db = Database()
