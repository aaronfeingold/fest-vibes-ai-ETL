"""
Service for loading scraped event data into the database.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List

from sentence_transformers import SentenceTransformer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.database import db
from shared.db.models import Artist, ArtistRelation, Event, Genre, Venue
from shared.schemas.dto import EventDTO
from shared.services.gcp_geocoding_service import geocoding_service
from shared.utils.configs import base_configs
from shared.utils.errors import DatabaseError
from shared.utils.logger import logger
from shared.utils.types import ErrorType


class DatabaseService:
    """
    Service for loading scraped event data into the database.
    """

    def __init__(self):
        """Initialize the database loader."""
        try:
            # Initialize SentenceTransformer with better error handling
            # Model should be pre-cached in container or will use /tmp cache
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Successfully loaded SentenceTransformer model")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model: {str(e)}")
            raise DatabaseError(
                message=f"Failed to initialize embedding model: {str(e)}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

    async def initialize(self):
        """Initialize the database connection and ensure tables exist."""
        await db.initialize()
        await db.create_tables()

    async def generate_embeddings_for_event(self, event: Event):
        """
        Generate text embeddings for an event.

        Args:
            event: Event object to generate embeddings for
        """
        try:
            if event.description:
                event.description_embedding = self.embedding_model.encode(
                    event.description
                )

            combined_text = (
                f"{event.artist_name} {event.venue_name} {event.description or ''}"
            )
            event.event_text_embedding = self.embedding_model.encode(combined_text)
            logger.debug(f"Generated embeddings for event: {event.artist_name}")
        except Exception as e:
            logger.error(
                f"Failed to generate embeddings for event {event.artist_name}: {str(e)}"
            )
            # Set empty embeddings as fallback to prevent database errors
            event.description_embedding = None
            event.event_text_embedding = None

    async def get_or_create_genre(self, session: AsyncSession, name: str) -> Genre:
        """
        Get or create a genre using PostgreSQL's ON CONFLICT for thread safety.

        This method prevents deadlocks when multiple concurrent processes try to
        create the same genre by using PostgreSQL's native ON CONFLICT clause.

        Args:
            session: Database session
            name: Name of the genre

        Returns:
            Genre object
        """
        try:
            # Use PostgreSQL's ON CONFLICT to handle concurrent inserts gracefully
            result = await session.execute(
                text(
                    """
                    INSERT INTO genres (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING id, name, description
                """
                ),
                {"name": name},
            )

            genre_row = result.fetchone()

            if genre_row:
                # Genre was just created, fetch it to get proper SQLAlchemy object
                result = await session.execute(select(Genre).filter_by(id=genre_row.id))
                return result.scalar_one()
            else:
                # Genre already existed, fetch it normally
                result = await session.execute(select(Genre).filter_by(name=name))
                return result.scalar_one()

        except Exception as e:
            logger.warning(f"Error in upsert for genre '{name}': {e}")
            # Fallback to simple select (genre should exist now)
            result = await session.execute(select(Genre).filter_by(name=name))
            genre = result.scalar_one_or_none()
            if not genre:
                # This should be very rare, but create as fallback
                logger.info(f"Fallback: Creating genre '{name}' after upsert failed")
                genre = Genre(name=name)
                session.add(genre)
                await session.flush()
            return genre

    async def upsert_artist(
        self, session: AsyncSession, artist_data, genre_objects: List[Genre]
    ) -> Artist:
        """
        Get or create an artist using PostgreSQL's ON CONFLICT for thread safety.

        This method prevents deadlocks when multiple concurrent processes try to
        create the same artist by using PostgreSQL's native ON CONFLICT clause.

        Args:
            session: Database session
            artist_data: ArtistData object with artist information
            genre_objects: List of Genre objects to associate with the artist

        Returns:
            Artist object
        """
        try:
            # Use PostgreSQL's ON CONFLICT to handle concurrent inserts gracefully
            result = await session.execute(
                text(
                    """
                    INSERT INTO artists (name, wwoz_artist_href, description, website)
                    VALUES (:name, :href, :description, :website)
                    ON CONFLICT (name) DO UPDATE SET
                        wwoz_artist_href = COALESCE(EXCLUDED.wwoz_artist_href, artists.wwoz_artist_href),
                        description = COALESCE(EXCLUDED.description, artists.description),
                        website = COALESCE(EXCLUDED.website, artists.website)
                    RETURNING id, name, wwoz_artist_href, description, website
                """
                ),
                {
                    "name": artist_data.name,
                    "href": artist_data.wwoz_artist_href,
                    "description": artist_data.description,
                    "website": artist_data.website,
                },
            )

            artist_row = result.fetchone()

            if artist_row:
                # Artist was created or updated, fetch it to get proper SQLAlchemy object
                result = await session.execute(
                    select(Artist).filter_by(id=artist_row.id)
                )
                artist = result.scalar_one()

                # Set genres if provided
                if genre_objects:
                    artist.genres = genre_objects

                return artist
            else:
                # Should not happen with RETURNING clause, but fallback
                result = await session.execute(
                    select(Artist).filter_by(name=artist_data.name)
                )
                artist = result.scalar_one()
                if genre_objects:
                    artist.genres = genre_objects
                return artist

        except Exception as e:
            logger.warning(f"Error in upsert for artist '{artist_data.name}': {e}")
            # Fallback to simple select (artist should exist now)
            result = await session.execute(
                select(Artist).filter_by(name=artist_data.name)
            )
            artist = result.scalar_one_or_none()
            if not artist:
                # This should be very rare, but create as fallback
                logger.info(
                    f"Fallback: Creating artist '{artist_data.name}' after upsert failed"
                )
                artist = Artist(
                    name=artist_data.name,
                    wwoz_artist_href=artist_data.wwoz_artist_href,
                    description=artist_data.description,
                    website=artist_data.website,
                    genres=genre_objects,
                )
                session.add(artist)
                await session.flush()
            elif genre_objects:
                artist.genres = genre_objects
            return artist

    async def upsert_venue(
        self, session: AsyncSession, venue_data, genre_objects: List[Genre]
    ) -> Venue:
        """
        Get or create a venue using PostgreSQL's ON CONFLICT for thread safety.

        This method prevents deadlocks when multiple concurrent processes try to
        create the same venue by using composite unique constraint (name + full_address).
        Handles geocoding efficiently by checking if it's needed.

        Args:
            session: Database session
            venue_data: VenueData object with venue information
            genre_objects: List of Genre objects to associate with the venue

        Returns:
            Venue object
        """
        try:
            # First check if venue exists to avoid unnecessary geocoding
            result = await session.execute(
                select(Venue).filter_by(
                    name=venue_data.name, full_address=venue_data.full_address
                )
            )
            existing_venue = result.scalar_one_or_none()

            if existing_venue:
                # Venue exists, check if it needs re-geocoding
                if existing_venue.needs_geocoding():
                    logger.info(f"Re-geocoding existing venue: {existing_venue.name}")
                    geolocation = await geocoding_service.geocode_address(
                        existing_venue.full_address
                    )
                    existing_venue.latitude = geolocation["latitude"]
                    existing_venue.longitude = geolocation["longitude"]
                    existing_venue.last_geocoded = datetime.now(
                        base_configs["timezone"]
                    )

                # Update genres if provided
                if genre_objects:
                    existing_venue.genres = genre_objects

                return existing_venue

            # Venue doesn't exist, create with geocoding
            logger.info(f"Creating new venue with geocoding: {venue_data.name}")
            geolocation = await geocoding_service.geocode_address(
                venue_data.full_address
            )

            # Determine indoor/streaming status
            venue_name_lower = venue_data.name.lower()
            is_indoors = "outdoor" not in venue_name_lower
            is_streaming = "streaming" in venue_name_lower

            # Use UPSERT to handle race conditions
            result = await session.execute(
                text(
                    """
                    INSERT INTO venues (name, phone_number, thoroughfare, locality, state,
                                       postal_code, full_address, wwoz_venue_href, website,
                                       is_active, latitude, longitude, last_geocoded,
                                       is_indoors, is_streaming)
                    VALUES (:name, :phone_number, :thoroughfare, :locality, :state,
                            :postal_code, :full_address, :wwoz_venue_href, :website,
                            :is_active, :latitude, :longitude, :last_geocoded,
                            :is_indoors, :is_streaming)
                    ON CONFLICT (name, full_address) DO UPDATE SET
                        phone_number = COALESCE(EXCLUDED.phone_number, venues.phone_number),
                        thoroughfare = COALESCE(EXCLUDED.thoroughfare, venues.thoroughfare),
                        locality = COALESCE(EXCLUDED.locality, venues.locality),
                        state = COALESCE(EXCLUDED.state, venues.state),
                        postal_code = COALESCE(EXCLUDED.postal_code, venues.postal_code),
                        wwoz_venue_href = COALESCE(EXCLUDED.wwoz_venue_href, venues.wwoz_venue_href),
                        website = COALESCE(EXCLUDED.website, venues.website),
                        is_active = EXCLUDED.is_active,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        last_geocoded = EXCLUDED.last_geocoded,
                        is_indoors = EXCLUDED.is_indoors,
                        is_streaming = EXCLUDED.is_streaming
                    RETURNING id
                """
                ),
                {
                    "name": venue_data.name,
                    "phone_number": venue_data.phone_number,
                    "thoroughfare": venue_data.thoroughfare,
                    "locality": venue_data.locality,
                    "state": venue_data.state,
                    "postal_code": venue_data.postal_code,
                    "full_address": venue_data.full_address,
                    "wwoz_venue_href": venue_data.wwoz_venue_href,
                    "website": venue_data.website,
                    "is_active": venue_data.is_active,
                    "latitude": geolocation["latitude"],
                    "longitude": geolocation["longitude"],
                    "last_geocoded": datetime.now(base_configs["timezone"]),
                    "is_indoors": is_indoors,
                    "is_streaming": is_streaming,
                },
            )

            venue_row = result.fetchone()

            if venue_row:
                # Fetch the complete venue object
                result = await session.execute(select(Venue).filter_by(id=venue_row.id))
                venue = result.scalar_one()

                # Set genres if provided
                if genre_objects:
                    venue.genres = genre_objects

                return venue
            else:
                # Race condition - venue was created by another process
                result = await session.execute(
                    select(Venue).filter_by(
                        name=venue_data.name, full_address=venue_data.full_address
                    )
                )
                venue = result.scalar_one()
                if genre_objects:
                    venue.genres = genre_objects
                return venue

        except Exception as e:
            logger.warning(f"Error in upsert for venue '{venue_data.name}': {e}")
            # Fallback to simple select
            result = await session.execute(
                select(Venue).filter_by(
                    name=venue_data.name, full_address=venue_data.full_address
                )
            )
            venue = result.scalar_one_or_none()
            if not venue:
                # Create as fallback (without UPSERT)
                logger.info(
                    f"Fallback: Creating venue '{venue_data.name}' after upsert failed"
                )
                geolocation = await geocoding_service.geocode_address(
                    venue_data.full_address
                )
                venue = Venue(
                    name=venue_data.name,
                    phone_number=venue_data.phone_number,
                    thoroughfare=venue_data.thoroughfare,
                    locality=venue_data.locality,
                    state=venue_data.state,
                    postal_code=venue_data.postal_code,
                    full_address=venue_data.full_address,
                    wwoz_venue_href=venue_data.wwoz_venue_href,
                    website=venue_data.website,
                    is_active=venue_data.is_active,
                    latitude=geolocation["latitude"],
                    longitude=geolocation["longitude"],
                    last_geocoded=datetime.now(base_configs["timezone"]),
                    genres=genre_objects,
                    is_indoors="outdoor" not in venue_data.name.lower(),
                    is_streaming="streaming" in venue_data.name.lower(),
                )
                session.add(venue)
                await session.flush()
            elif genre_objects:
                venue.genres = genre_objects
            return venue

    async def upsert_event(
        self,
        session: AsyncSession,
        event_data,
        artist: Artist,
        venue: Venue,
        genres: List[Genre],
    ) -> Event:
        """
        Get or create an event using PostgreSQL's ON CONFLICT for thread safety.

        This method prevents deadlocks when multiple concurrent processes try to
        create the same event by using wwoz_event_href as unique constraint.

        Args:
            session: Database session
            event_data: EventData object with event information
            artist: Artist object for the event
            venue: Venue object for the event
            genres: List of Genre objects to associate with the event

        Returns:
            Event object
        """
        try:
            # Check if event already exists
            if event_data.wwoz_event_href:
                result = await session.execute(
                    select(Event).filter_by(wwoz_event_href=event_data.wwoz_event_href)
                )
                existing_event = result.scalar_one_or_none()

                if existing_event:
                    # Event exists, optionally update fields
                    if event_data.description and not existing_event.description:
                        existing_event.description = event_data.description

                    # Update genres if provided
                    if genres:
                        existing_event.genres = genres

                    return existing_event

            # Create new event
            is_indoors = "outdoor" not in venue.name.lower()
            is_streaming = "streaming" in venue.name.lower()

            new_event = Event(
                wwoz_event_href=event_data.wwoz_event_href,
                description=event_data.description,
                artist_id=artist.id,
                venue_id=venue.id,
                artist_name=artist.name,
                venue_name=venue.name,
                performance_time=event_data.event_date,
                scrape_time=datetime.now(base_configs["timezone"]),
                genres=genres,
                is_indoors=is_indoors,
                is_streaming=is_streaming,
            )

            # Generate embeddings for the new event
            await self.generate_embeddings_for_event(new_event)

            session.add(new_event)
            await session.flush()  # Get the ID for relationships

            return new_event

        except Exception as e:
            logger.warning(
                f"Error in upsert for event '{event_data.wwoz_event_href}': {e}"
            )

            # Fallback: check if event was created by another process
            if event_data.wwoz_event_href:
                result = await session.execute(
                    select(Event).filter_by(wwoz_event_href=event_data.wwoz_event_href)
                )
                existing_event = result.scalar_one_or_none()
                if existing_event:
                    return existing_event

            # If still no event found, re-raise the exception
            raise

    async def _ensure_genres_exist(self, events: List[EventDTO]):
        """
        Pre-create all unique genres in a single transaction to prevent deadlocks.

        Args:
            events: List of events to extract genre names from
        """
        all_genres = set()
        for event in events:
            all_genres.update(event.event_data.genres)

        if not all_genres:
            return

        async with db.session() as session:
            try:
                logger.info(f"Pre-creating {len(all_genres)} unique genres")
                for genre_name in all_genres:
                    await self.get_or_create_genre(session, genre_name)
                await session.commit()
                logger.info("Successfully pre-created all genres")
            except Exception as e:
                logger.warning(f"Error pre-creating genres: {e}")
                await session.rollback()
                # Continue anyway - individual batches will handle genre creation

    async def _process_event_batch_with_retry(
        self, batch: List[EventDTO]
    ) -> Dict[str, int]:
        """
        Process a batch with deadlock retry logic.

        Args:
            batch: Small list of events to process together

        Returns:
            Summary of operations performed
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await self._process_event_batch(batch)
            except Exception as e:
                error_str = str(e).lower()
                if (
                    "deadlock" in error_str
                    or "lock timeout" in error_str
                    or "concurrent update" in error_str
                ) and attempt < max_retries - 1:

                    # Exponential backoff with jitter
                    delay = 0.1 * (2**attempt) + (
                        0.05 * attempt
                    )  # 0.1, 0.25, 0.55 seconds
                    logger.warning(
                        f"Deadlock detected on attempt {attempt + 1}, retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(f"Failed after {attempt + 1} attempts: {str(e)}")
                raise

    async def _process_event_batch(self, batch: List[EventDTO]) -> Dict[str, int]:
        """
        Process a small batch of events in a single transaction.

        Args:
            batch: Small list of events to process together

        Returns:
            Summary of operations performed
        """
        summary = {
            "artists_created": 0,
            "venues_created": 0,
            "events_created": 0,
            "genres_created": 0,
        }
        batch_start_time = time.time()

        async with db.session() as session:
            try:
                for event in batch:
                    logger.info(
                        f"Processing: {event.artist_data.name} at {event.venue_data.name}"
                    )

                    # Fetch or create genres (should already exist from pre-seeding)
                    genre_objects = []
                    for genre_name in event.event_data.genres:
                        genre = await self.get_or_create_genre(session, genre_name)
                        genre_objects.append(genre)

                    # Upsert artist using new method
                    artist = await self.upsert_artist(
                        session, event.artist_data, genre_objects
                    )
                    if (
                        hasattr(artist, "_sa_instance_state")
                        and artist._sa_instance_state.pending
                    ):
                        summary["artists_created"] += 1

                    # Upsert venue using new method
                    venue = await self.upsert_venue(
                        session, event.venue_data, genre_objects
                    )
                    if (
                        hasattr(venue, "_sa_instance_state")
                        and venue._sa_instance_state.pending
                    ):
                        summary["venues_created"] += 1

                    # Handle related artists (simplified for now)
                    for related_artist_data in event.event_data.related_artists:
                        if (
                            isinstance(related_artist_data, dict)
                            and "name" in related_artist_data
                        ):
                            related_name = related_artist_data["name"]
                        else:
                            related_name = str(related_artist_data)

                        related_artist_result = await session.execute(
                            select(Artist).filter_by(name=related_name)
                        )
                        related_artist = related_artist_result.scalar_one_or_none()

                        if not related_artist:
                            related_artist = Artist(name=related_name)
                            session.add(related_artist)
                            await session.flush()
                            summary["artists_created"] += 1

                        # Check if relation exists
                        relation_exists = await session.execute(
                            select(ArtistRelation).filter_by(
                                artist_id=artist.id,
                                related_artist_id=related_artist.id,
                            )
                        )
                        if not relation_exists.scalar_one_or_none():
                            session.add(
                                ArtistRelation(
                                    artist_id=artist.id,
                                    related_artist_id=related_artist.id,
                                )
                            )

                    # Upsert event using new method
                    event_obj = await self.upsert_event(
                        session, event.event_data, artist, venue, genre_objects
                    )
                    if (
                        hasattr(event_obj, "_sa_instance_state")
                        and event_obj._sa_instance_state.pending
                    ):
                        summary["events_created"] += 1

                await session.commit()

                # Log performance metrics
                batch_duration = time.time() - batch_start_time
                logger.info(
                    f"Batch processed in {batch_duration:.2f}s - "
                    + f"Artists: {summary['artists_created']}, "
                    + f"Venues: {summary['venues_created']}, "
                    + f"Events: {summary['events_created']}"
                )

                return summary

            except Exception as e:
                await session.rollback()
                batch_duration = time.time() - batch_start_time
                logger.error(f"Batch failed after {batch_duration:.2f}s: {str(e)}")

                # Check if this is a constraint violation that we should handle gracefully
                error_str = str(e).lower()
                if "duplicate key" in error_str or "constraint" in error_str:
                    logger.warning(
                        f"Constraint violation in batch processing: {str(e)}"
                    )
                    # Re-raise to trigger retry logic in the wrapper

                raise

    async def save_events(self, events: List[EventDTO]) -> Dict[str, int]:
        """
        Save events to the database using optimized transaction batching.

        This method implements a two-phase approach:
        1. Pre-create all genres to prevent deadlocks
        2. Process events in small batches to minimize lock contention

        Args:
            events: List of events to save

        Returns:
            Dictionary containing operation summaries
        """
        operation_summary = {
            "artists_created": 0,
            "venues_created": 0,
            "genres_created": 0,
            "events_created": 0,
        }

        start_time = time.time()

        try:
            logger.info(f"Starting optimized batch processing of {len(events)} events")

            # Phase 1: Pre-create all unique genres in single transaction
            await self._ensure_genres_exist(events)

            # Phase 2: Process events in small batches to minimize lock contention
            batch_size = 5  # Small batches = shorter lock times
            failed_batches = 0
            total_batches = (len(events) + batch_size - 1) // batch_size

            for i in range(0, len(events), batch_size):
                batch = events[i : i + batch_size]
                batch_num = i // batch_size + 1

                try:
                    logger.info(f"Processing batch {batch_num}/{total_batches}")
                    # Use retry wrapper for deadlock handling
                    batch_summary = await self._process_event_batch_with_retry(batch)

                    # Aggregate results
                    for key in operation_summary:
                        operation_summary[key] += batch_summary.get(key, 0)

                    logger.info(f"Batch {batch_num} completed successfully")

                except Exception as e:
                    failed_batches += 1
                    logger.error(f"Batch {batch_num} failed after retries: {str(e)}")
                    # Continue with next batch instead of failing entire job
                    continue

            # Final performance report
            total_duration = time.time() - start_time
            successful_batches = total_batches - failed_batches

            logger.info(f"Batch processing completed in {total_duration:.2f}s")
            logger.info(f"Success rate: {successful_batches}/{total_batches} batches")
            logger.info(
                f"Total created - Artists: {operation_summary['artists_created']}, "
                + f"Venues: {operation_summary['venues_created']}, "
                + f"Events: {operation_summary['events_created']}"
            )

            if failed_batches > 0:
                logger.warning(f"Completed with {failed_batches} failed batches")
            else:
                logger.info("All batches completed successfully")

            return operation_summary

        except Exception as e:
            logger.error(f"Critical error in save_events: {str(e)}")
            raise DatabaseError(
                message=f"Critical error saving event data: {str(e)}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

    async def close(self):
        """Close database connection."""
        await db.close()
