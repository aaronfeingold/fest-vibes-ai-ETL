#!/usr/bin/env python3
"""
Backfill Existing Embeddings Script
Created: 2025-08-13
Purpose: Generate vector embeddings for existing artists, venues, and genres in the database

This script should be run after the add_vector_embeddings_to_core_tables.sql migration
to populate embeddings for all existing data.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from loader.service import DatabaseService  # noqa: E402
from shared.db.database import db  # noqa: E402
from shared.db.models import Artist, Genre, Venue  # noqa: E402
from shared.utils.logger import logger  # noqa: E402

# Configure logging for this script
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class EmbeddingBackfillService:
    """Service to backfill embeddings for existing data."""

    def __init__(self):
        """Initialize the backfill service."""
        self.db_service = None
        self.stats = {
            "artists_processed": 0,
            "venues_processed": 0,
            "genres_processed": 0,
            "artists_updated": 0,
            "venues_updated": 0,
            "genres_updated": 0,
            "errors": 0,
        }

    async def initialize(self):
        """Initialize database connection and service."""
        await db.initialize()
        self.db_service = DatabaseService()
        logger.info("Backfill service initialized successfully")

    async def get_entities_without_embeddings(
        self, session: AsyncSession
    ) -> Dict[str, List]:
        """Get all entities that don't have embeddings yet."""
        from sqlalchemy.orm import selectinload

        # Get artists without embeddings (with genres preloaded)
        artists_result = await session.execute(
            select(Artist)
            .options(selectinload(Artist.genres))
            .where(Artist.description_embedding.is_(None))
        )
        artists = artists_result.scalars().all()

        # Get venues without embeddings (with genres preloaded)
        venues_result = await session.execute(
            select(Venue)
            .options(selectinload(Venue.genres))
            .where(Venue.venue_info_embedding.is_(None))
        )
        venues = venues_result.scalars().all()

        # Get genres without embeddings
        genres_result = await session.execute(
            select(Genre).where(Genre.genre_embedding.is_(None))
        )
        genres = genres_result.scalars().all()

        return {
            "artists": list(artists),
            "venues": list(venues),
            "genres": list(genres),
        }

    async def backfill_genre_embeddings(
        self, session: AsyncSession, genres: List[Genre]
    ):
        """Backfill embeddings for genres."""
        logger.info(f"Starting backfill for {len(genres)} genres")

        for genre in genres:
            try:
                self.stats["genres_processed"] += 1

                # Generate embedding
                await self.db_service.generate_embeddings_for_genre(genre)

                if genre.genre_embedding is not None:
                    self.stats["genres_updated"] += 1
                    logger.debug(f"Generated embedding for genre: {genre.name}")

                # Commit every 10 genres to avoid long transactions
                if self.stats["genres_processed"] % 10 == 0:
                    await session.commit()
                    logger.info(
                        f"Processed {self.stats['genres_processed']}/{len(genres)} genres"
                    )

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error processing genre {genre.name}: {str(e)}")
                continue

        # Final commit
        await session.commit()
        logger.info(
            f"Completed genre backfill: {self.stats['genres_updated']}/{len(genres)} updated"
        )

    async def backfill_artist_embeddings(
        self, session: AsyncSession, artists: List[Artist]
    ):
        """Backfill embeddings for artists."""
        logger.info(f"Starting backfill for {len(artists)} artists")

        for artist in artists:
            try:
                self.stats["artists_processed"] += 1

                # Genres should be preloaded via selectinload

                # Generate embedding
                await self.db_service.generate_embeddings_for_artist(artist)

                if artist.description_embedding is not None:
                    self.stats["artists_updated"] += 1
                    logger.debug(f"Generated embedding for artist: {artist.name}")

                # Commit every 10 artists to avoid long transactions
                if self.stats["artists_processed"] % 10 == 0:
                    await session.commit()
                    logger.info(
                        f"Processed {self.stats['artists_processed']}/{len(artists)} artists"
                    )

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error processing artist {artist.name}: {str(e)}")
                continue

        # Final commit
        await session.commit()
        logger.info(
            f"Completed artist backfill: {self.stats['artists_updated']}/{len(artists)} updated"
        )

    async def backfill_venue_embeddings(
        self, session: AsyncSession, venues: List[Venue]
    ):
        """Backfill embeddings for venues."""
        logger.info(f"Starting backfill for {len(venues)} venues")

        for venue in venues:
            try:
                self.stats["venues_processed"] += 1

                # Genres should be preloaded via selectinload

                # Generate embedding
                await self.db_service.generate_embeddings_for_venue(venue)

                if venue.venue_info_embedding is not None:
                    self.stats["venues_updated"] += 1
                    logger.debug(f"Generated embedding for venue: {venue.name}")

                # Commit every 10 venues to avoid long transactions
                if self.stats["venues_processed"] % 10 == 0:
                    await session.commit()
                    logger.info(
                        f"Processed {self.stats['venues_processed']}/{len(venues)} venues"
                    )

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error processing venue {venue.name}: {str(e)}")
                continue

        # Final commit
        await session.commit()
        logger.info(
            f"Completed venue backfill: {self.stats['venues_updated']}/{len(venues)} updated"
        )

    async def run_backfill(self):
        """Run the complete backfill process."""
        logger.info("Starting embedding backfill process")

        try:
            async with db.session() as session:
                # Get all entities without embeddings
                entities = await self.get_entities_without_embeddings(session)

                total_entities = (
                    len(entities["artists"])
                    + len(entities["venues"])
                    + len(entities["genres"])
                )
                logger.info(f"Found {total_entities} entities to backfill:")
                logger.info(f"  - Artists: {len(entities['artists'])}")
                logger.info(f"  - Venues: {len(entities['venues'])}")
                logger.info(f"  - Genres: {len(entities['genres'])}")

                if total_entities == 0:
                    logger.info("No entities need embedding backfill. All done!")
                    return

                # Backfill in order: Genres first (they're referenced by others)
                if entities["genres"]:
                    await self.backfill_genre_embeddings(session, entities["genres"])

                # Then artists
                if entities["artists"]:
                    await self.backfill_artist_embeddings(session, entities["artists"])

                # Finally venues
                if entities["venues"]:
                    await self.backfill_venue_embeddings(session, entities["venues"])

                # Final statistics
                logger.info("=== BACKFILL COMPLETE ===")
                logger.info(
                    f"Artists: {self.stats['artists_updated']}/{self.stats['artists_processed']} updated"
                )
                logger.info(
                    f"Venues: {self.stats['venues_updated']}/{self.stats['venues_processed']} updated"
                )
                logger.info(
                    f"Genres: {self.stats['genres_updated']}/{self.stats['genres_processed']} updated"
                )
                logger.info(f"Errors: {self.stats['errors']}")

                if self.stats["errors"] > 0:
                    logger.warning(
                        f"Completed with {self.stats['errors']} errors - check logs above"
                    )
                else:
                    logger.info("All entities processed successfully!")

        except Exception as e:
            logger.error(f"Critical error during backfill: {str(e)}")
            raise

        finally:
            if self.db_service:
                await self.db_service.close()
            await db.close()


async def main():
    """Main function to run the backfill."""
    backfill_service = EmbeddingBackfillService()

    try:
        await backfill_service.initialize()
        await backfill_service.run_backfill()

    except KeyboardInterrupt:
        logger.info("Backfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backfill failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    print("Starting Vector Embeddings Backfill Process...")
    print("This will generate embeddings for all existing artists, venues, and genres.")
    print("Press Ctrl+C to cancel.\n")

    # Give user a chance to cancel
    try:
        asyncio.sleep(3)
    except KeyboardInterrupt:
        print("Cancelled by user")
        sys.exit(0)

    asyncio.run(main())
