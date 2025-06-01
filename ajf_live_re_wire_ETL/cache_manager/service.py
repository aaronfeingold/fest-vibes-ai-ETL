"""
Service for managing cache operations.
"""

from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload  # noqa: F401

from ajf_live_re_wire_ETL.shared.cache.redis_cache import redis_cache
from ajf_live_re_wire_ETL.shared.db.database import db
from ajf_live_re_wire_ETL.shared.db.models import Artist, Event
from ajf_live_re_wire_ETL.shared.schemas.dto import (
    ArtistData,
    EventData,
    EventDTO,
    VenueData,
)
from ajf_live_re_wire_ETL.shared.utils.errors import DatabaseError, RedisError
from ajf_live_re_wire_ETL.shared.utils.logger import logger
from ajf_live_re_wire_ETL.shared.utils.types import ErrorType


class CacheManager:
    """
    Service for managing Redis cache operations.
    """

    async def initialize(self):
        """Initialize database connection."""
        await db.initialize()

    async def get_events_by_date(self, date_str: str) -> List[EventDTO]:
        """
        Get events from the database for a specific date.

        Args:
            date_str: Date string in format YYYY-MM-DD

        Returns:
            List of Event objects
        """
        try:
            # Parse the date string
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Calculate start and end of the day
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            # Query the events
            async with db.session() as session:
                result = await session.execute(
                    select(Event)
                    .options(
                        selectinload(Event.venue),
                        selectinload(Event.artist).joinedload(Artist.genres),
                        selectinload(Event.artist).joinedload(Artist.related_artists),
                        selectinload(Event.genres),
                    )
                    .filter(Event.performance_time >= start_datetime)
                    .filter(Event.performance_time <= end_datetime)
                    .order_by(Event.performance_time)
                )

                db_events = result.scalars().all()
                logger.info(f"Found {len(db_events)} events for date {date_str}")

                # Convert to EventDTO objects
                events = []
                for event in db_events:
                    # Create VenueData
                    venue = event.venue
                    venue_data = VenueData(
                        name=venue.name,
                        thoroughfare=venue.thoroughfare or "",
                        phone_number=venue.phone_number or "",
                        locality=venue.locality or "New Orleans",
                        state=venue.state or "",
                        postal_code=venue.postal_code or "",
                        full_address=venue.full_address or "",
                        is_active=venue.is_active,
                        website=venue.website or "",
                        wwoz_venue_href=venue.wwoz_venue_href or "",
                    )

                    # Create ArtistData
                    artist = event.artist
                    artist_data = ArtistData(
                        name=artist.name,
                        description=artist.description or "",
                        wwoz_artist_href=artist.wwoz_artist_href or "",
                        genres=[genre.name for genre in artist.genres],
                        related_artists=[
                            rel_artist.name for rel_artist in artist.related_artists
                        ],
                    )

                    # Create EventData
                    event_data = EventData(
                        event_date=event.performance_time.date(),
                        wwoz_event_href=event.wwoz_event_href or "",
                        event_artist=event.artist_name,
                        description=event.description or "",
                        genres=[genre.name for genre in event.genres],
                    )

                    # Create EventDTO
                    event_dto = EventDTO(
                        artist_data=artist_data,
                        venue_data=venue_data,
                        event_data=event_data,
                        performance_time=event.performance_time,
                        scrape_time=event.scrape_time,
                    )

                    events.append(event_dto)

                return events

        except Exception as e:
            logger.error(f"Error retrieving events from database: {str(e)}")
            raise DatabaseError(
                message=f"Error retrieving events from database: {str(e)}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

    async def update_cache_for_date(self, date_str: str) -> int:
        """
        Update the Redis cache for a specific date.

        Args:
            date_str: Date string in format YYYY-MM-DD

        Returns:
            Number of events cached
        """
        try:
            # Get events from the database
            events = await self.get_events_by_date(date_str)

            # Cache the events in Redis
            success = await redis_cache.set_events(date_str, events)

            if not success:
                raise RedisError(
                    message=f"Failed to cache events for date {date_str}",
                    error_type=ErrorType.REDIS_ERROR,
                    status_code=500,
                )

            logger.info(f"Successfully cached {len(events)} events for date {date_str}")
            return len(events)

        except (DatabaseError, RedisError) as e:
            logger.error(f"Error updating cache for date {date_str}: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating cache: {str(e)}")
            raise RedisError(
                message=f"Unexpected error updating cache: {str(e)}",
                error_type=ErrorType.REDIS_ERROR,
                status_code=500,
            )

    async def update_cache_for_date_range(
        self, start_date: str, end_date: str
    ) -> Dict[str, int]:
        """
        Update the Redis cache for a range of dates.

        Args:
            start_date: Start date string in format YYYY-MM-DD
            end_date: End date string in format YYYY-MM-DD

        Returns:
            Dictionary mapping dates to number of events cached
        """
        # Parse dates
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Validate date range
        if start > end:
            raise ValueError("Start date must be before or equal to end date")

        # Update cache for each date in the range
        results = {}
        current_date = start
        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            try:
                event_count = await self.update_cache_for_date(date_str)
                results[date_str] = event_count
            except Exception as e:
                logger.error(f"Error updating cache for {date_str}: {str(e)}")
                results[date_str] = -1  # Indicate error

            current_date += timedelta(days=1)

        return results

    async def close(self):
        """Close database connection."""
        await db.close()
