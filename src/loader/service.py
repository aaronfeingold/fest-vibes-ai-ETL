"""
Service for loading scraped event data into the database.
"""

from datetime import datetime
from typing import Dict, List

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
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
        Get or create a genre.

        Args:
            session: Database session
            name: Name of the genre

        Returns:
            Genre object
        """
        result = await session.execute(select(Genre).filter_by(name=name))
        genre = result.scalar_one_or_none()
        if not genre:
            genre = Genre(name=name)
            session.add(genre)
        return genre

    async def save_events(self, events: List[EventDTO]) -> Dict[str, int]:
        """
        Save events to the database.

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

        async with db.session() as session:
            try:
                logger.info(f"Starting to save {len(events)} events to database")
                for idx, event in enumerate(events, 1):
                    logger.info(f"Event: {event}")
                    logger.info(
                        f"Processing event {idx}/{len(events)}: {event.artist_data.name} at {event.venue_data.name}"
                    )

                    # Fetch or create genres
                    genre_objects = []
                    for genre_name in event.event_data.genres:
                        genre = await self.get_or_create_genre(session, genre_name)
                        if genre.id is None:  # New genre was created
                            operation_summary["genres_created"] += 1
                        genre_objects.append(genre)
                    logger.info(f"Created/fetched {len(genre_objects)} genres")

                    # Check if event is indoors and/or streaming
                    venue_name = event.venue_data.name.lower()
                    is_indoors = "outdoor" not in venue_name
                    is_streaming = "streaming" in venue_name

                    # Fetch or create venue
                    venue_result = await session.execute(
                        select(Venue).filter_by(name=event.venue_data.name)
                    )
                    venue = venue_result.scalar_one_or_none()

                    if not venue:
                        logger.info(f"Creating new venue: {event.venue_data.name}")
                        geolocation = await geocoding_service.geocode_address(
                            event.venue_data.full_address
                        )
                        venue = Venue(
                            name=event.venue_data.name,
                            phone_number=event.venue_data.phone_number,
                            thoroughfare=event.venue_data.thoroughfare,
                            locality=event.venue_data.locality,
                            state=event.venue_data.state,
                            postal_code=event.venue_data.postal_code,
                            full_address=event.venue_data.full_address,
                            wwoz_venue_href=event.venue_data.wwoz_venue_href,
                            website=event.venue_data.website,
                            is_active=event.venue_data.is_active,
                            latitude=geolocation["latitude"],
                            longitude=geolocation["longitude"],
                            last_geocoded=datetime.now(base_configs["timezone"]),
                            genres=genre_objects,
                            is_indoors=is_indoors,
                            is_streaming=is_streaming,
                        )
                        session.add(venue)
                        await session.flush()
                        operation_summary["venues_created"] += 1
                        logger.info(f"Created venue with ID: {venue.id}")
                    elif venue.needs_geocoding():
                        logger.info(f"Re-geocoding venue: {venue.name}")
                        geolocation = await geocoding_service.geocode_address(
                            venue.full_address
                        )
                        venue.latitude = geolocation["latitude"]
                        venue.longitude = geolocation["longitude"]
                        venue.last_geocoded = datetime.now(base_configs["timezone"])

                    # Fetch or create main artist
                    logger.info(f"Processing artist: {event.artist_data.name}")
                    artist_result = await session.execute(
                        select(Artist).filter_by(name=event.artist_data.name)
                    )
                    artist = artist_result.scalar_one_or_none()

                    if not artist:
                        artist = Artist(
                            name=event.artist_data.name,
                            wwoz_artist_href=event.artist_data.wwoz_artist_href,
                            description=event.artist_data.description,
                            genres=genre_objects,
                            website=event.artist_data.website,
                        )
                        session.add(artist)
                        await session.flush()
                        operation_summary["artists_created"] += 1
                        logger.info(f"Created artist with ID: {artist.id}")

                    # Handle related artists
                    for related_artist in event.event_data.related_artists:
                        logger.info(
                            f"Processing related artist for {event.artist_data.name}: {related_artist['name']}"
                        )

                        related_artist_result = await session.execute(
                            select(Artist).filter_by(name=related_artist["name"])
                        )
                        related_artist_record = (
                            related_artist_result.scalar_one_or_none()
                        )

                        if not related_artist_record:
                            related_artist_record = Artist(name=related_artist["name"])
                            session.add(related_artist_record)
                            await session.flush()
                            operation_summary["artists_created"] += 1
                            logger.info(
                                f"Created related artist with ID: {related_artist_record.id}"
                            )

                        # Check if relation already exists
                        relation_exists = await session.execute(
                            select(ArtistRelation).filter_by(
                                artist_id=artist.id,
                                related_artist_id=related_artist_record.id,
                            )
                        )
                        if relation_exists.scalar_one_or_none() is None:
                            session.add(
                                ArtistRelation(
                                    artist_id=artist.id,
                                    related_artist_id=related_artist_record.id,
                                )
                            )
                            logger.info(
                                f"Created artist relation between {artist.id} and {related_artist_record.id}"
                            )

                    # Upsert event
                    existing_event = await session.execute(
                        select(Event).where(
                            Event.wwoz_event_href == event.event_data.wwoz_event_href
                        )
                    )
                    existing_event = existing_event.scalar_one_or_none()

                    if not existing_event:
                        new_event = Event(
                            wwoz_event_href=event.event_data.wwoz_event_href,
                            description=event.event_data.description,
                            artist_id=artist.id,
                            venue_id=venue.id,
                            artist_name=event.artist_data.name,
                            venue_name=event.venue_data.name,
                            performance_time=datetime.fromisoformat(
                                event.performance_time
                            ),
                            scrape_time=datetime.fromisoformat(event.scrape_time),
                            genres=genre_objects,
                            is_indoors=is_indoors,
                            is_streaming=is_streaming,
                        )

                        # Generate embeddings for the new event
                        logger.info("Generating embeddings for event")
                        await self.generate_embeddings_for_event(new_event)
                        session.add(new_event)
                        await session.flush()
                        operation_summary["events_created"] += 1
                        logger.info(f"Created event with ID: {new_event.id}")

                logger.info("Committing all changes to database")
                await session.commit()
                logger.info("Successfully committed all changes")
                return operation_summary
            except Exception as e:
                logger.error(f"Error saving event data to database: {str(e)}")
                await session.rollback()
                logger.info("Rolled back database changes due to error")
                raise DatabaseError(
                    message=f"Error saving event data to database: {str(e)}",
                    error_type=ErrorType.DATABASE_ERROR,
                    status_code=500,
                )

    async def close(self):
        """Close database connection."""
        await db.close()
