import os
import re
import json
import logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import redis
from botocore.exceptions import ClientError
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlencode
from datetime import datetime, date
import pytz
from typing import Dict, Any, List, TypedDict, Union, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Index,
    ForeignKey,
    Float,
    Interval,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, Session
import aiohttp
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
from pathlib import Path
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
from pgvector.sqlalchemy import Vector
import boto3


load_dotenv()  # Load variables from .env

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define the sample website to scrape
# TODO: scrape from many sites...
SAMPLE_WEBSITE = os.environ.get("BASE_URL", "https://example.com")
SAMPLE_ENDPOINT = "/calendar/livewire-music"
# Define the timezone for New Orleans (CST/CDT),
# since current version is New Orleans' events specific
NEW_ORLEANS_TZ = pytz.timezone("America/Chicago")
# Current date format for query params...subject to change on the website's whims
WWOZ_DATE_FORMAT = "%Y-%m-%d"

# Default headers for HTTP requests to prevent Bot detection
DEFAULT_HEADERS = {
    "User-Agent": os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36",
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# TODO: make more use of these key-value pairs in the fn for analytics...
class LambdaContext:
    aws_request_id: str
    log_stream_name: str
    function_name: str
    function_version: str
    memory_limit_in_mb: int
    invoked_function_arn: str
    remaining_time_in_millis: int


class AwsInfo(TypedDict):
    aws_request_id: str
    log_stream_name: str


class SuccessResponseBase(TypedDict):
    status: str
    data: Any
    date: str


class ErrorResponseBase(TypedDict):
    status: str
    error: Dict[str, str]


# Define the response types
SuccessResponse = Union[SuccessResponseBase, AwsInfo]
ErrorResponse = Union[ErrorResponseBase, AwsInfo]
ResponseBody = Union[SuccessResponse, ErrorResponse]


class ResponseType(TypedDict):
    statusCode: int
    headers: Dict[str, str]
    body: ResponseBody


# Keep track of the error types
class ErrorType(Enum):
    GENERAL_ERROR = "GENERAL_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    URL_ERROR = "URL_ERROR"
    FETCH_ERROR = "FETCH_ERROR"
    NO_EVENTS = "NO_EVENTS"
    PARSE_ERROR = "PARSE_ERROR"
    SOUP_ERROR = "SOUP_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    AWS_ERROR = "AWS_ERROR"
    VALUE_ERROR = "VALUE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    GOOGLE_MAPS_API_ERROR = "GOOGLE_MAPS_API_ERROR"


class ScrapingError(Exception):
    """Custom exception for DeepScraper errors"""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.GENERAL_ERROR,
        status_code: int = 500,
    ):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseHandlerError(Exception):
    """Custom exception for when the Database Handler errors"""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.DATABASE_ERROR,
        status_code: int = 500,
    ):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)


Base = declarative_base()


# Database Models
class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    phone_number = Column(String)
    thoroughfare = Column(String)
    locality = Column(String)
    state = Column(String)
    postal_code = Column(String)
    full_address = Column(String)
    wwoz_venue_href = Column(String)
    website = Column(String)
    is_active = Column(Boolean, default=True)
    latitude = Column(Float)
    longitude = Column(Float)
    capacity = Column(Integer)
    is_indoor = Column(Boolean, default=True)
    last_updated = Column(DateTime(timezone=True), server_default="now()")
    last_geocoded = Column(DateTime(timezone=True))  # Track when we last geocoded this venue

    # Fixed relationships
    genres = relationship("Genre", secondary="venue_genres", back_populates="venues")
    events = relationship("Event", back_populates="venue")
    artists = relationship("Artist", secondary="venue_artists", back_populates="venues")

    @hybrid_property
    def full_url(self):
        return urljoin(SAMPLE_WEBSITE, self.wwoz_venue_href)

    def needs_geocoding(self) -> bool:
        """Check if venue needs geocoding"""
        if not self.latitude or not self.longitude:
            return True
        if not self.last_geocoded:
            return True
        # Re-geocode if it's been more than 30 days
        return (datetime.now(NEW_ORLEANS_TZ) - self.last_geocoded).days > 30


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    wwoz_artist_href = Column(String)
    description = Column(String)
    popularity_score = Column(Float)
    typical_set_length = Column(Interval)

    # Fixed relationships
    events = relationship("Event", back_populates="artist")
    venues = relationship("Venue", secondary="venue_artists", back_populates="artists")
    genres = relationship("Genre", secondary="artist_genres", back_populates="artists")
    related_artists = relationship(
        "Artist",
        secondary="artist_relations",
        primaryjoin="Artist.id==ArtistRelation.artist_id",
        secondaryjoin="Artist.id==ArtistRelation.related_artist_id",
        back_populates="related_by_artists",
    )
    related_by_artists = relationship(
        "Artist",
        secondary="artist_relations",
        primaryjoin="Artist.id==ArtistRelation.related_artist_id",
        secondaryjoin="Artist.id==ArtistRelation.artist_id",
        back_populates="related_artists",
    )


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    wwoz_event_href = Column(String)
    description = Column(String)
    artist_id = Column(Integer, ForeignKey("artists.id"))
    venue_id = Column(Integer, ForeignKey("venues.id"))
    artist_name = Column(String)
    venue_name = Column(String)
    performance_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    scrape_time = Column(Date, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default="now()")
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String)
    is_indoors = Column(Boolean, default=True)  # Default to indoors
    is_streaming = Column(Boolean, default=False)
    # Add vector embedding columns
    description_embedding = Column(Vector(384))  # Using all-MiniLM-L6-v2 model
    event_text_embedding = Column(Vector(384))  # Combined text for semantic search

    # Fixed relationships
    artist = relationship("Artist", back_populates="events")
    venue = relationship("Venue", back_populates="events")
    genres = relationship("Genre", secondary="event_genres", back_populates="events")

    @hybrid_property
    def full_url(self):
        return urljoin(SAMPLE_WEBSITE, self.wwoz_event_href)


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    # Fixed relationships
    venues = relationship("Venue", secondary="venue_genres", back_populates="genres")
    artists = relationship("Artist", secondary="artist_genres", back_populates="genres")
    events = relationship("Event", secondary="event_genres", back_populates="genres")


# Join Tables - Added missing foreign key constraints and cascades
class ArtistRelation(Base):
    __tablename__ = "artist_relations"

    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    related_artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_artist_relation_artist_id", artist_id),
        Index("ix_artist_relation_related_artist_id", related_artist_id),
    )


class VenueArtist(Base):
    __tablename__ = "venue_artists"

    venue_id = Column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_venue_artist_venue_id", venue_id),
        Index("ix_venue_artist_artist_id", artist_id),
    )


class VenueGenre(Base):
    __tablename__ = "venue_genres"

    venue_id = Column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = Column(
        Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_venue_genre_venue_id", venue_id),
        Index("ix_venue_genre_genre_id", genre_id),
    )


class ArtistGenre(Base):
    __tablename__ = "artist_genres"

    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = Column(
        Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_artist_genre_artist_id", artist_id),
        Index("ix_artist_genre_genre_id", genre_id),
    )


class EventGenre(Base):
    __tablename__ = "event_genres"

    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = Column(
        Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_event_genre_event_id", event_id),
        Index("ix_event_genre_genre_id", genre_id),
    )


# Data Transfer Objects
@dataclass
class VenueData:
    name: str = ""
    thoroughfare: str = ""
    phone_number: str = ""
    locality: str = "New Orleans"  # Today, local. Tomorrow, the world
    state: str = ""
    postal_code: str = ""
    full_address: str = ""
    is_active: Boolean = True
    website: str = ""
    wwoz_venue_href: str = ""
    event_artist: str = ""


@dataclass
class ArtistData:
    name: str = ""
    description: str = "lorum ipsum"  # TODO: USE OPENAI TO SUMMARIZE and EXTRACT
    genres: List[str] = field(default_factory=list)
    related_artists: List[str] = field(default_factory=list)
    wwoz_artist_href: str = ""


@dataclass
class EventData:
    event_date: datetime
    wwoz_event_href: str = ""
    event_artist: str = ""
    wwoz_artist_href: str = ""
    description: str = ""
    related_artists: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)


@dataclass
class EventDTO:
    artist_data: ArtistData
    venue_data: VenueData
    event_data: EventData
    performance_time: datetime
    scrape_time: date


class EventDTOEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (EventDTO, VenueData, ArtistData, EventData)):
            return asdict(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


class Services:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    async def geocode_address(self, address: str) -> dict:
        default_NOLA_coords = {
            "latitude": 29.9511,
            "longitude": -90.0715,
        }
        # Check if address is empty or for streaming events
        if not address or address.strip() == "" or ".Streaming" in address:
            logger.info(
                f"Address is empty or for streaming event: {address=}. Using default coordinates."
            )
            # Return default coordinates (could be New Orleans center coordinates)
            return default_NOLA_coords

        logger.info(f"Geocoding {address=}")
        params = {"address": address, "key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()

                    if data["status"] == "OK":
                        result = data["results"][0]
                        lat = result["geometry"]["location"]["lat"]
                        lng = result["geometry"]["location"]["lng"]

                        return {"latitude": lat, "longitude": lng}
                    else:
                        logger.warning(
                            f"Geocoding failed: {data['status']} - "
                            f"{data.get('error_message')}. Using default coordinates."
                        )
                        # Return default coordinates instead of raising an error
                        return default_NOLA_coords
        except Exception as e:
            logger.warning(
                f"Exception during geocoding: {str(e)}. Using default coordinates."
            )
            # Return default coordinates instead of raising an error
            return default_NOLA_coords


class DatabaseHandler(Services):
    def __init__(self, engine, async_session):
        super().__init__()
        self.engine = engine
        self.AsyncSession = async_session
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

    @classmethod
    async def create(cls):
        try:
            db_url = os.getenv("PG_DATABASE_URL")
            if not db_url:
                raise ValueError("Database URL not found in environment variables")

            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            engine = create_async_engine(
                db_url,
                echo=False,  # Set to True for debugging
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
            )

            async_session = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )

            self = cls(engine, async_session)
            await self.create_tables()
            return self
        except Exception as e:
            logger.error(f"Failed to create DatabaseHandler: {str(e)}")
            raise

    @asynccontextmanager
    async def get_session(self):
        """Context manager for handling sessions"""
        session = self.AsyncSession()
        try:
            logger.info("Starting new database session")
            yield session
            logger.info("Session yielded, attempting to commit")
            await session.commit()
            logger.info("Session committed successfully")
        except Exception as e:
            logger.error(f"Error in database session: {str(e)}")
            await session.rollback()
            logger.error("Session rolled back due to error")
            raise
        finally:
            logger.info("Closing database session")
            await session.close()
            logger.info("Database session closed")

    async def create_tables(self):
        try:
            async with self.engine.begin() as conn:
                # Enable pgvector extension
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))

                # Check if tables exist
                result = await conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'events'
                    )
                """))
                tables_exist = result.scalar()

                if not tables_exist:
                    logger.info("Tables don't exist, creating them...")
                    await conn.run_sync(Base.metadata.create_all)
                    logger.info("Tables created successfully")
                else:
                    logger.info("Tables already exist, skipping creation")

        except SQLAlchemyError as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise

    async def get_or_create_genre(self, session: AsyncSession, name: str):
        result = await session.execute(select(Genre).filter_by(name=name))
        genre = result.scalar_one_or_none()
        if not genre:
            genre = Genre(name=name)
            session.add(genre)
        return genre

    # Embeddings are handled by DBHandler because we may want to embed other models the same way.
    async def generate_embeddings_for_event(self, event: Event):
        """Generate embeddings for an event"""
        if event.description:
            event.description_embedding = self.embedding_model.encode(event.description)

        combined_text = f"{event.artist_name} {event.venue_name} {event.description or ''}"
        event.event_text_embedding = self.embedding_model.encode(combined_text)

    async def save_events(self, events: List[EventDTO], scrape_time: date):
        async with self.get_session() as session:
            try:
                logger.info(f"Starting to save {len(events)} events to database")
                for idx, event in enumerate(events, 1):
                    logger.info(
                        f"Processing event {idx}/{len(events)}: {event.artist_data.name} at {event.venue_data.name}"
                    )

                    # Fetch or create genres
                    genre_objects = []
                    for genre_name in event.event_data.genres:
                        genre = await self.get_or_create_genre(session, genre_name)
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
                        geolocation = await self.geocode_address(
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
                            last_geocoded=datetime.now(NEW_ORLEANS_TZ),
                            genres=genre_objects,
                        )
                        session.add(venue)
                        await session.flush()
                        logger.info(f"Created venue with ID: {venue.id}")
                    elif venue.needs_geocoding():
                        logger.info(f"Re-geocoding venue: {venue.name}")
                        geolocation = await self.geocode_address(venue.full_address)
                        venue.latitude = geolocation["latitude"]
                        venue.longitude = geolocation["longitude"]
                        venue.last_geocoded = datetime.now(NEW_ORLEANS_TZ)

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
                        )
                        session.add(artist)
                        await session.flush()
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
                            logger.info(
                                f"Created related artist with ID: {related_artist_record.id}"
                            )

                        # Explicitly create artist relations
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
                            performance_time=event.performance_time,
                            scrape_time=scrape_time,
                            genres=genre_objects,
                            is_indoors=is_indoors,
                            is_streaming=is_streaming,
                        )

                        # Generate embeddings for the new event
                        logger.info("Generating embeddings for event")
                        await self.generate_embeddings_for_event(new_event)
                        session.add(new_event)
                        await session.flush()
                        logger.info(f"Created event with ID: {new_event.id}")

                logger.info("Committing all changes to database")
                await session.commit()
                logger.info("Successfully committed all changes")
            except Exception as e:
                logger.error(f"Error saving event data to database: {str(e)}")
                await session.rollback()
                logger.info("Rolled back database changes due to error")
                raise DatabaseHandlerError(
                    message=f"Error saving event data to database: {str(e)}",
                    error_type=ErrorType.DATABASE_ERROR,
                    status_code=500,
                )

    def get_events(
        session: Session, start_date: datetime, end_date: datetime
    ) -> List[Event]:
        """
        Retrieve all events occurring in a specific range of dates.
        :param session: SQLAlchemy session
        :param start_date: The start of the date range
        :param end_date: The end of the date range
        :return: List of events
        """
        # Query the database for events within the date range
        try:
            events = (
                session.query(Event)
                .filter(
                    Event.performance_time >= start_date,
                    Event.performance_time <= end_date,
                )
                .all()
            )

            return events
        except Exception as e:
            session.rollback()
            raise DatabaseHandlerError(
                message=f"An unexpected error occurred while getting events from DB: {e}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

    async def close(self):
        """Cleanup method to properly close the engine"""
        await self.engine.dispose()

    async def inspect_embeddings(self, limit: int = 5):
        """Inspect vector embeddings from the database"""
        async with self.get_session() as session:
            try:
                # Query events with non-null embeddings
                result = await session.execute(
                    text("""
                        SELECT id, artist_name, venue_name,
                               description_embedding::text,
                               event_text_embedding::text
                        FROM events
                        WHERE description_embedding IS NOT NULL
                           OR event_text_embedding IS NOT NULL
                        LIMIT :limit
                    """),
                    {"limit": limit}
                )

                rows = result.fetchall()
                return [
                    {
                        "id": row[0],
                        "artist": row[1],
                        "venue": row[2],
                        "description_embedding": row[3],
                        "event_text_embedding": row[4]
                    }
                    for row in rows
                ]
            except Exception as e:
                raise DatabaseHandlerError(
                    message=f"Error inspecting embeddings: {str(e)}",
                    error_type=ErrorType.DATABASE_ERROR,
                    status_code=500,
                )


class DeepScraper:
    def __init__(self):
        self.session = None
        self.seen_urls = set()

    async def run(self, params: Dict[str, str]) -> List[EventDTO]:
        try:
            html = await self.fetch_html(self.generate_url(params))
            return await self.parse_html(html, params["date"])
        except ScrapingError:
            raise
        except Exception as e:
            logger.error(f"A {ErrorType.GENERAL_ERROR.value} occurred : {e}")
            raise

    def generate_url(
        self,
        params: Dict[str, str] = {},
        endpoint: str = SAMPLE_ENDPOINT,
        base_url: str = SAMPLE_WEBSITE,
    ) -> str:
        try:
            # First join the base URL with the endpoint
            url = urljoin(base_url, endpoint)
            # Then add query parameters if they exist
            if params:
                url = f"{url}?{urlencode(params)}"
            return url
        except (TypeError, Exception) as e:
            raise ScrapingError(
                message=f"Failed to create URL: {e}",
                error_type=ErrorType.GENERAL_ERROR,
                status_code=500,
            )

    async def fetch_html(self, url: str) -> str:
        if not self.session:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.get(url, headers=DEFAULT_HEADERS) as response:
                if response.status != 200:
                    raise ScrapingError(
                        message=f"Failed to fetch data: HTTP {response.status}",
                        error_type=ErrorType.HTTP_ERROR,
                        status_code=response.status,
                    )
                return await response.text()
        except HTTPError as e:
            raise ScrapingError(
                message=f"Failed to fetch data: HTTP {e.code}",
                error_type=ErrorType.HTTP_ERROR,
                status_code=e.code,
            )
        except URLError as e:
            raise ScrapingError(
                message=f"Failed to connect to server: {e.reason}",
                error_type=ErrorType.URL_ERROR,
                status_code=503,
            )
        except Exception as e:
            raise ScrapingError(
                message=f"An unexpected error occurred while fetching data: {e}",
                error_type=ErrorType.FETCH_ERROR,
                status_code=500,
            )

    async def make_soup(self, endpoint: str) -> BeautifulSoup:
        try:
            html = await self.fetch_html(self.generate_url({}, endpoint))
            return BeautifulSoup(html, "html.parser")
        except ScrapingError as e:
            raise ScrapingError(
                error_type=e.error_type,
                message=f"Failed to create soup from html: {e.message}",
                status_code=e.status_code,
            )
        except Exception as e:
            raise ScrapingError(
                message=f"An exception making soup: {e}",
                error_type=ErrorType.SOUP_ERROR,
                status_code=500,
            )

    def get_text_or_default(self, element, tag, class_name, default=""):
        found = element.find(tag, class_=class_name)
        return found.text.strip() if found else default

    async def get_venue_data(self, wwoz_venue_href: str, venue_name: str) -> VenueData:
        """Deep crawl venue page to get additional details"""
        print("running get venue data")
        if wwoz_venue_href in self.seen_urls:
            # don't build details again, we already have seen this URL today
            return {}

        self.seen_urls.add(wwoz_venue_href)
        soup = await self.make_soup(wwoz_venue_href)
        venue_data = VenueData(
            name=venue_name,
            wwoz_venue_href=wwoz_venue_href,
            is_active=True,
        )
        # find the content div if exists
        content_div = soup.find("div", class_="content")

        if content_div is not None:
            try:
                venue_data.thoroughfare = self.get_text_or_default(
                    content_div, "div", "thoroughfare"
                )
                venue_data.locality = self.get_text_or_default(
                    content_div, "span", "locality"
                )
                venue_data.state = self.get_text_or_default(
                    content_div, "span", "state"
                )
                venue_data.postal_code = self.get_text_or_default(
                    content_div, "span", "postal_code"
                )

                website_div = content_div.find(
                    "div", class_="field-name-field-url"
                )  # this div is not always present, if it is, then get the href

                if website_div is not None:
                    website_link = website_div.find("div", class_="field-item even")
                    venue_data.website = (
                        website_link.find("a")["href"] if website_link else ""
                    )
                phone_section = content_div.find("div", class_="field-name-field-phone")
                if phone_section is not None:
                    venue_data.phone_number = phone_section.find("a").text.strip()
                # create a full address to transfer to geolocation API
                venue_data.full_address = f"""{venue_data.thoroughfare}, {venue_data.locality},
                    {venue_data.state} {venue_data.postal_code}"""
                # find out if business is still active...if it has events then of course it is
                # that being said, TODO: we could be scraping all the WWOZ venues in a future iteration
                # in which we may find some that are now inactive
                status_div = content_div.find(
                    "div", class_="field-name-field-organization-status"
                )
                if status_div is not None:
                    status = self.get_text_or_default(
                        status_div, "div", "field-item even", "Active"
                    )
                    venue_data.is_active = True if status.lower() == "active" else False
            except Exception as e:
                raise ScrapingError(
                    message=f"Failed to scrape venue content section for address, website, phone etc etc: {e}",
                    error_type=ErrorType.PARSE_ERROR,
                    status_code=400,
                )

        return venue_data

    def is_attribute_non_empty(
        self,
        obj,
        attr_name,
    ):
        if hasattr(obj, attr_name):  # Check if the attribute exists
            value = getattr(obj, attr_name)  # Get the attribute value
            return (
                isinstance(value, str) and value != ""
            )  # Check if it's a non-empty string
        return False

    async def get_artist_data(
        self, wwoz_artist_href: str, artist_name: str
    ) -> ArtistData:
        """Deep crawl artist page to get additional details"""
        print(f"running get artist data. {artist_name=}")
        if wwoz_artist_href in self.seen_urls:
            return ArtistData(
                name=artist_name,
                wwoz_artist_href=wwoz_artist_href,
            )

        self.seen_urls.add(wwoz_artist_href)
        soup = await self.make_soup(wwoz_artist_href)

        artist_data = ArtistData(
            name=artist_name,
            wwoz_artist_href=wwoz_artist_href,
        )

        content_div = soup.select_one(".content")

        if content_div is not None:
            try:
                genres_div = content_div.find("div", class_="field-name-field-genres")
                # hopefully the artist has some genres listed...otherwise we just get some description,
                # related acts (not always, and no need for deep crawl), and move along
                if genres_div is not None:
                    artist_data.genres = [
                        genre.text.strip() for genre in genres_div.find_all("a")
                    ]

                related_artists_div = content_div.find(
                    "div", class_="field field-name-field-related-acts"
                )

                if related_artists_div is not None:
                    related_artists_list = related_artists_div.find(
                        "span", _class="textformatter-list"
                    )
                    artist_data.related_artists = [
                        related_artist.text.strip()
                        for related_artist in related_artists_list.find_all("a")
                    ]
                # TODO: GRAB THE ARTIST'S DESCRIPTION HERE (w/ OPENAI to Summarize perhaps?)
            except Exception as e:
                raise ScrapingError(
                    message=f"Failed to scrape artist content section for genres, related acts etc: {e}",
                    error_type=ErrorType.PARSE_ERROR,
                    status_code=400,
                )

        return artist_data

    async def get_event_data(
        self, wwoz_event_href: str, artist_name: str, event_date: datetime
    ) -> tuple[EventData, ArtistData]:
        """Deep crawl venue page to get additional details"""
        print("running get event data")
        if wwoz_event_href in self.seen_urls:
            return EventData(
                event_date=event_date,
                wwoz_event_href=wwoz_event_href,
                event_artist=artist_name,
            ), ArtistData(name=artist_name)

        # TODO: CLEAN UP EXCESS VARS
        self.seen_urls.add(wwoz_event_href)
        soup = await self.make_soup(wwoz_event_href)

        event_data = EventData(
            event_date=event_date,
            wwoz_event_href=wwoz_event_href,
            event_artist=artist_name,
        )

        event_div = soup.find("div", class_="content")
        if event_div is not None:
            description_div = event_div.find("div", class_="field-name-body")
            try:
                description_field = description_div.find(
                    "div", class_="field-item even"
                )
                # TODO: USE OPENAI API TO EXTRACT EVENT DETAILS FROM DESCRIPTION
                # IE 21+, Ticket Price, other websites (ticket, bands, event, etc)
                description = description_field.find("p").text.strip()
                # add whatever description we have to the event data
                event_data.description = description
            except Exception as e:
                # if we error getting these things, who cares, just pass and default to no description
                logger.warning(f"Failed to scrape event description aka lagniappe: {e}")
                pass

            related_artists_div = event_div.find(
                "div", class_=re.compile(r"field-name-field-related-acts")
            )
            # find the artist name in the related artist links if links exist
            related_artists = []
            if related_artists_div:
                related_artists_list = related_artists_div.find(
                    "span", class_="textformatter-list"
                )
                # TODO: if artist not in DB, add them
                # now, we have no DB so whatever
                # add all other artists in list that do match the artist as 'related artists'
                for link in related_artists_list.find_all("a"):
                    if link.text.strip() not in artist_name:
                        related_artists.append(
                            {
                                "name": link.text.strip(),
                                "wwoz_artist_href": link["href"],
                            }
                        )
                    else:
                        # sometimes the artist name of the event artist has no link
                        # if it does, let's grab some more info, whatever there is, hopefully some genres
                        event_data.wwoz_artist_href = link["href"]
            # copy the related artists to the event data if any -\()_()/-
            event_data.related_artists = related_artists
        artist_data = ArtistData(name=artist_name)

        if self.is_attribute_non_empty(event_data, "wwoz_artist_href"):
            artist_data = await self.get_artist_data(
                event_data.wwoz_artist_href, artist_name
            )

        # for now, let's just get the genres of the event artist if we have this info scraped
        # and give the event some genres for people to search by
        try:
            genre_list_empty = True
            if hasattr(artist_data, "genres"):  # Check if the attribute exists
                value = getattr(artist_data, "genres")  # Get the attribute value
                genre_list_empty = (
                    isinstance(value, tuple) and len(value) == 0
                )  # Check if it's a non-empty string
                if not genre_list_empty:
                    event_data.genres = artist_data.genres
        except Exception as e:
            raise ScrapingError(
                message=f"Failed to add artist's genres to the event description: {e}",
                error_type=ErrorType.PARSE_ERROR,
                status_code=400,
            )

        return event_data, artist_data

    def parse_event_performance_time(self, date_str: str, time_str: str) -> datetime:
        # Extract the relevant date and time portion
        try:
            # Parse the time string, e.g. "8:00pm"
            time_stripped = time_str.strip()
            time_pattern = r"\b\d{1,2}:\d{2}\s?(am|pm)\b"
            match = re.search(time_pattern, time_stripped, re.IGNORECASE)
            # default to 12:00am if no time is found
            extracted_time = match.group() if match else "12:00am"
            # Combine the date and time into a full string
            combined_str = f"{date_str} {extracted_time}"  # e.g., "1-5-2025 8:00pm"

            # Parse the combined string into a naive datetime
            naive_datetime = datetime.strptime(combined_str, "%Y-%m-%d %I:%M%p")

            # Localize to the central timezone
            localized_datetime = NEW_ORLEANS_TZ.localize(naive_datetime)
            return localized_datetime
        except Exception as e:
            raise ValueError(
                f"Error parsing datetime string: {date_str}  and time {time_str}: {e}"
            ) from e

    async def parse_html(self, html: str, date_str: str) -> List[EventDTO]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            events = []
            livewire_listing = soup.find("div", class_="livewire-listing")

            if not livewire_listing:
                logger.warning("No livewire-listing found on the page.")
                raise ScrapingError(
                    message="No events found for this date",
                    error_type=ErrorType.NO_EVENTS,
                    status_code=404,
                )

            for panel in livewire_listing.find_all("div", class_="panel panel-default"):
                # Venue name is each panel's title
                panel_title = panel.find("h3", class_="panel-title")
                # Extract venue info
                if panel_title is None:
                    print("WARNING NO TITLE")
                    logger.warning("Panel is missing Venue Name...This is unexpected.")
                # parse text to get venue name
                venue_name = (
                    panel_title.find("a").text.strip()
                    if panel_title
                    else "Unknown Venue"
                )

                print(f"venue name: {venue_name}")
                # get wwoz's venue href from the venue name
                wwoz_venue_href = panel_title.find("a")["href"]
                # use href to get details, and return the original href in the venue data
                # TODO: If venue not in DB, get info about it
                # TODO: else if last updated over 1 month, get updated info
                # TODO: for now, just get the venue details to prototype
                venue_data = await self.get_venue_data(wwoz_venue_href, venue_name)
                # find the panel's body to ensure we are only dealing with the correct rows
                panel_body = panel.find("div", class_="panel-body")

                for row in panel_body.find_all("div", class_="row"):
                    calendar_info = row.find("div", class_="calendar-info")
                    if not calendar_info:
                        continue
                    # the event link inner text is the artist name, not a link to the artists page though
                    # is the link to more event details ie related acts, which can be link to the artist, but not always
                    wwoz_event_link = calendar_info.find("a")
                    if not wwoz_event_link:
                        continue
                    # get artist name and wwoz event href
                    event_artist_name = wwoz_event_link.text.strip()
                    wwoz_event_href = wwoz_event_link["href"]
                    # use the href to for the event to scrape deeper for more details on artists, and return any
                    event_data, artist_data = await self.get_event_data(
                        wwoz_event_href, event_artist_name, datetime.strptime(date_str, "%Y-%m-%d").date()
                    )
                    # Extract time string
                    time_str = calendar_info.find_all("p")[1].text.strip()
                    # the performance time had ought to be known
                    performance_time = (
                        self.parse_event_performance_time(date_str, time_str)
                        if time_str
                        else None
                    )

                    event = EventDTO(
                        artist_data=artist_data,
                        venue_data=venue_data,
                        event_data=event_data,
                        performance_time=performance_time,
                        scrape_time=datetime.now(NEW_ORLEANS_TZ).date(),
                    )
                    events.append(event)

            return events
        except ScrapingError:
            raise
        except Exception as e:
            raise ScrapingError(
                message=f"Failed to parse webpage content: {e}",
                error_type=ErrorType.PARSE_ERROR,
                status_code=500,
            )


class FileHandler:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.s3_bucket = os.getenv('S3_BUCKET_NAME', 'ajf-live-re-wire-data')

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and injection attacks.
        """
        # Remove any path traversal attempts
        filename = filename.replace('../', '').replace('..\\', '')
        # Remove any non-alphanumeric characters except - and _
        filename = re.sub(r'[^a-zA-Z0-9\-_]', '', filename)
        return filename

    @staticmethod
    async def cleanup_local_files(filepath: str) -> None:
        """
        Clean up local files after they've been uploaded to S3.
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Successfully cleaned up local file: {filepath}")
        except Exception as e:
            logger.error(f"Error cleaning up local file {filepath}: {str(e)}")
            # Don't raise the error - we don't want cleanup failures to affect the main flow

    @staticmethod
    async def save_events_local(
        events: List[EventDTO],
        *,
        date_str: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Save events to a local JSON file for development purposes.
        Creates a 'data' directory in the project root if it doesn't exist.

        Args:
            events: List of EventDTO objects to save
            date_str: Optional date string to include in filename
            filename: Optional custom filename to use
        """
        print("running save_events_local")
        # Setup data directory in project root
        data_dir = Path(__file__).resolve().parent / "data"
        data_dir.mkdir(exist_ok=True)

        # Generate or use provided filename
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if date_str:
                # Sanitize the date_str before using it in filename
                safe_date = FileHandler.sanitize_filename(date_str)
                filename = f"event_data_{safe_date}_{timestamp}.json"
            else:
                filename = f"event_data_{timestamp}.json"
        else:
            # Sanitize any provided filename
            filename = FileHandler.sanitize_filename(filename)

        # Ensure .json extension
        if not filename.endswith(".json"):
            filename += ".json"

        # Ensure the final path is within the data directory
        filepath = data_dir / filename
        try:
            # Verify the filepath is within the data directory
            filepath.resolve().relative_to(data_dir.resolve())
        except ValueError:
            raise ValueError("Invalid file path - attempted path traversal")

        print(f"{filepath=}")
        # Save to file
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(events, f, cls=EventDTOEncoder, indent=2, ensure_ascii=False)

        return str(filepath)

    async def upload_to_s3(self, filepath: str) -> str:
        """
        Upload a file to S3 bucket.
        Returns the S3 URL of the uploaded file.
        """
        try:
            # Get just the filename from the full path
            filename = Path(filepath).name

            # Create a unique key for S3 using timestamp and filename
            timestamp = datetime.now().strftime("%Y/%m/%d")
            s3_key = f"raw_events/{timestamp}/{filename}"

            logger.info(f"Uploading {filepath} to S3 bucket {self.s3_bucket} with key {s3_key}")

            # Upload the file
            self.s3_client.upload_file(
                filepath,
                self.s3_bucket,
                s3_key,
                ExtraArgs={'ContentType': 'application/json'}
            )

            # Generate the S3 URL
            s3_url = f"s3://{self.s3_bucket}/{s3_key}"
            logger.info(f"Successfully uploaded file to {s3_url}")

            # Clean up the local file after successful upload
            await self.cleanup_local_files(filepath)

            return s3_url

        except Exception as e:
            logger.error(f"Error uploading file to S3: {str(e)}")
            raise

    @staticmethod
    async def load_events_local() -> List[EventDTO]:
        """
        Load events from a local JSON file for development purposes.
        """
        data_dir = Path(__file__).resolve().parent / "data"
        # Get the most recently created file in the data directory
        latest_file = max(data_dir.glob("*.json"), key=os.path.getctime)

        if not latest_file.exists():
            raise FileNotFoundError(f"File not found: {latest_file}")

        with latest_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        def dict_to_event(event_dict: dict) -> EventDTO:
            artist_data = ArtistData(**event_dict["artist_data"])
            venue_data = VenueData(**event_dict["venue_data"])
            event_data = EventData(**event_dict["event_data"])

            return EventDTO(
                artist_data=artist_data,
                venue_data=venue_data,
                event_data=event_data,
                performance_time=datetime.fromisoformat(event_dict["performance_time"]),
                scrape_time=date.fromisoformat(event_dict["scrape_time"]),
            )

        return [dict_to_event(event) for event in data]


class RedisCacheHandler:
    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        # Parse the Redis URL
        if redis_url.startswith('redis://'):
            # Remove the redis:// prefix
            redis_url = redis_url[8:]
            # Split into host and port
            host, port = redis_url.split(':')
            self.redis_client = redis.Redis(
                host=host,
                port=int(port),
                decode_responses=True
            )
        else:
            # Fallback to direct host:port format
            self.redis_client = redis.Redis(
                host=redis_url, port=6379, decode_responses=True
            )

    def _get_cache_key(self, date_str: str) -> str:
        """Generate a cache key for a specific date"""
        return f"events:{date_str}"

    def _get_ttl(self, date_str: str) -> Optional[int]:
        """Calculate TTL based on date string"""
        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            days_diff = (event_date - today).days

            if days_diff == 0:
                return 86400  # 24 hours for today
            elif days_diff > 0:
                return None  # no TTL for future dates
            else:
                return 86400  # 24 hours for historical (optional)
        except ValueError as e:
            logger.error(f"Invalid date format: {date_str}. Error: {e}")
            return None

    async def cache_events(self, date_str: str, events: List[EventDTO]) -> None:
        """Cache events for a specific date with appropriate TTL"""
        try:
            cache_key = self._get_cache_key(date_str)
            events_json = json.dumps(events, cls=EventDTOEncoder)

            existing = self.redis_client.get(cache_key)

            if existing:
                existing_data = json.loads(existing)
                new_data = json.loads(events_json)

                if existing_data == new_data:
                    # Data hasn't changed
                    event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    today = datetime.now().date()
                    if event_date == today:
                        # But it's today, so renew TTL anyway
                        self.redis_client.expire(cache_key, 86400)
                        logger.info(f"Refreshed TTL for today's data: {date_str}")
                    else:
                        logger.info(
                            f"No change detected for {date_str}, skipping cache update"
                        )
                    return

            ttl = self._get_ttl(date_str)
            if ttl:
                self.redis_client.setex(cache_key, ttl, events_json)
            else:
                self.redis_client.set(cache_key, events_json)
            logger.info(f"Cached events for {date_str} with TTL {ttl} seconds")
        except Exception as e:
            logger.error(f"Error caching events for {date_str}: {str(e)}")
            # Don't raise the exception - let the main flow continue even if caching fails

    async def get_cached_events(self, date_str: str) -> Optional[List[EventDTO]]:
        """Retrieve cached events for a specific date"""
        cache_key = self._get_cache_key(date_str)
        cached_data = self.redis_client.get(cache_key)

        if cached_data:
            logger.info(f"Cache hit for {date_str}")
            events_data = json.loads(cached_data)
            return [EventDTO(**event) for event in events_data]

        logger.info(f"Cache miss for {date_str}")
        return None

    async def clear_cache(self, date_str: str) -> None:
        """Clear cache for a specific date"""
        cache_key = self._get_cache_key(date_str)
        self.redis_client.delete(cache_key)
        logger.info(f"Cleared cache for {date_str}")


class Utilities(FileHandler):
    def __init__(self):
        super().__init__()
        pass

    @staticmethod
    def generate_response(status_code: int, body: ResponseBody) -> ResponseType:
        if isinstance(body.get("error", {}).get("type"), ErrorType):
            body["error"]["type"] = body["error"]["type"].value

        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": body,
        }

    @staticmethod
    def generate_date_str() -> str:
        try:
            date_param = datetime.now(NEW_ORLEANS_TZ).date()
            date_format = os.getenv("WWOZ_DATE_FORMAT", WWOZ_DATE_FORMAT)
            return date_param.strftime(date_format)
        except (ValueError, Exception) as e:
            msg = f"Error generating a date for params: {e}"
            logger.error(msg)
            raise ScrapingError(
                message=msg,
                error_type=(
                    ErrorType.VALUE_ERROR
                    if isinstance(e, ValueError)
                    else ErrorType.GENERAL_ERROR
                ),
                status_code=400,
            )

    # TODO: add more validation for the various query string parameters
    @staticmethod
    def validate_params(query_string_params: Dict[str, str] = {}) -> Dict[str, str]:
        # validate the date parameter (only 1 parameter is expected as of now)
        # TODO: abstract logic per parameter
        logger.info("Validating query string parameters")
        date_param = query_string_params.get("date")
        if date_param:
            logger.info(
                f"Date parameter found, validating format for WWOZ params: {date_param}"
            )
            try:
                datetime.strptime(date_param, WWOZ_DATE_FORMAT).date()
            except ValueError as e:
                raise ScrapingError(
                    message=f"Invalid date format: {e}",
                    error_type=ErrorType.VALUE_ERROR,
                    status_code=400,
                )
        else:
            logger.info("No date parameter found. Generating a new date.")
            date_param = Utilities.generate_date_str()

        return {**query_string_params, "date": date_param}


class Controllers(Utilities):
    def __init__(self):
        super().__init__()

    @staticmethod
    async def create_events(
        aws_info: AwsInfo, event: Dict[str, Any], dev_env=False
    ) -> ResponseType:
        db_handler = None
        try:
            # validate the parameters
            params = Utilities.validate_params(event.get("queryStringParameters", {}))
            scrape_time = datetime.now(NEW_ORLEANS_TZ).date()  # Convert to date for DB storage

            if not dev_env:
                logger.info("running DeepScraper")
                deep_scraper = DeepScraper()
                events = await deep_scraper.run(params)

                # Cache the events in Redis
                redis_cache = RedisCacheHandler()
                await redis_cache.cache_events(params["date"], events)

                logger.info("save JSON output to file")
                # save JSON output to file for debugging
                file_handler = FileHandler()
                filepath = await file_handler.save_events_local(
                    events=events,
                    date_str=params["date"]
                )
                logger.info(f"Saved event data to file: {filepath}")

                # Upload to S3 if not in dev environment
                try:
                    s3_url = await file_handler.upload_to_s3(filepath)
                    logger.info(f"Successfully uploaded event data to S3: {s3_url}")
                except Exception as e:
                    logger.error(f"Failed to upload to S3: {str(e)}")
                    # Continue execution even if S3 upload fails
            else:
                # in development, load events from file for debugging
                events = await Utilities.load_events_local()

            # Save to database
            logger.info("running DatabaseHandler.save_events")
            db_handler = await DatabaseHandler.create()
            await db_handler.save_events(events, scrape_time)
            logger.info("finished saving events to DB")

            return Utilities.generate_response(
                200,
                {
                    "status": "success",
                    "data": json.dumps(events, cls=EventDTOEncoder),
                    "scrape_time": scrape_time.strftime(WWOZ_DATE_FORMAT),
                    **aws_info,
                },
            )
        except ScrapingError as e:
            logger.error(f"Scraping error: {e.error_type} - {e.message}")
            return Utilities.generate_response(
                e.status_code,
                {
                    "status": "error",
                    "error": {
                        "type": e.error_type,
                        "message": e.message,
                    },
                    **aws_info,
                },
            )
        except HTTPError as e:
            error = ScrapingError(
                message=f"Failed to fetch data: HTTP {e.code}",
                error_type=ErrorType.HTTP_ERROR,
                status_code=e.code,
            )
            logger.error(f"HTTP error: {error.message}")
            return Utilities.generate_response(
                error.status_code,
                {
                    "status": "error",
                    "error": {
                        "type": error.error_type,
                        "message": error.message,
                    },
                    **aws_info,
                },
            )
        except ClientError as e:
            error_message = e.response["Error"]["Message"]
            error_code = e.response["Error"]["Code"]
            logger.error(f"AWS ClientError: {error_code} - {error_message}")
            return Utilities.generate_response(
                500,
                {
                    "status": "error",
                    "error": {
                        "type": ErrorType.AWS_ERROR,
                        "message": f"AWS error occurred: {error_message}",
                    },
                    **aws_info,
                },
            )
        except DatabaseHandlerError as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Utilities.generate_response(
                e.status_code,
                {
                    "status": "error",
                    "error": {
                        "type": e.error_type,
                        "message": e.message,
                    },
                    **aws_info,
                },
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Utilities.generate_response(
                500,
                {
                    "status": "error",
                    "error": {
                        "type": ErrorType.UNKNOWN_ERROR,
                        "message": f"An unexpected error occurred: {e}",
                    },
                    **aws_info,
                },
            )
        finally:
            if db_handler:  # Only close if db_handler was successfully initialized
                await db_handler.close()

    @staticmethod
    async def get_events(date_str: Optional[str] = None) -> ResponseType:
        """Get events, trying Redis cache first, then falling back to database"""
        try:
            # If no date specified, use today's date
            if not date_str:
                date_str = datetime.now(NEW_ORLEANS_TZ).strftime("%Y-%m-%d")

            # Try Redis cache first
            redis_cache = RedisCacheHandler()
            cached_events = await redis_cache.get_cached_events(date_str)

            if cached_events:
                logger.info(f"Returning cached events for {date_str}")
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "status": "success",
                        "data": cached_events,
                        "source": "cache"
                    })
                }

            # If not in cache, get from database
            logger.info(f"Cache miss for {date_str}, fetching from database")
            db_handler = await DatabaseHandler.create()
            events = await db_handler.get_events(date_str)

            # Cache the results for future requests
            await redis_cache.cache_events(date_str, events)

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "success",
                    "data": events,
                    "source": "database"
                })
            }
        except Exception as e:
            logger.error(f"Error getting events: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "status": "error",
                    "error": str(e)
                })
            }


async def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> ResponseType:
    # record the AWS request ID and log stream name for all responses...
    aws_info = {
        "aws_request_id": context.aws_request_id,
        "log_stream_name": context.log_stream_name,
    }
    # POST and GET To AWS API Gateway only; reuses the same image
    http_method = event.get("httpMethod", "GET")
    try:
        if http_method == "POST":
            return await Controllers.create_events(
                aws_info, event, dev_env=event.get("devEnv", False)
            )
        elif http_method == "GET":
            return Controllers.get_events()
        else:
            return Controllers.generate_response(
                400,
                {
                    "status": "error",
                    "error": "Invalid HTTP method",
                },
            )
    except Exception as e:
        return Controllers.generate_response(500, {"status": "error", "error": str(e)})
