"""
Database utility for connecting to and interacting with the database.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from ..config import config
from ..errors import DatabaseError, ErrorType
from ..models.base import Base

logger = logging.getLogger(__name__)


class Database:
    """
    Database connection manager.
    """

    def __init__(self):
        """Initialize the database connection."""
        self.engine = None
        self.async_session = None

    async def initialize(self):
        """Initialize the database engine and session maker."""
        try:
            db_url = config.db.url
            if not db_url:
                raise ValueError("Database URL not found in configuration")

            # Detect SSL requirement
            parsed_url = urlparse(db_url)
            hostname = parsed_url.hostname or ""
            # Default to no SSL unless explicitly needed
            use_ssl = "neon" in hostname or "aws" in hostname

            # Convert to async-compatible URL if needed
            if not db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

            connect_args = {"ssl": use_ssl} if use_ssl else {}

            self.engine = create_async_engine(
                db_url,
                echo=config.db.echo,
                pool_size=config.db.pool_size,
                max_overflow=config.db.max_overflow,
                pool_timeout=config.db.pool_timeout,
                connect_args=connect_args,
            )

            self.async_session = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

            # Verify connection
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))

            logger.info("Successfully initialized database connection")

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
