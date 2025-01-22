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
from typing import Dict, Any, List, TypedDict, Union
from enum import Enum
from dataclasses import dataclass, field
from sqlalchemy import (
    create_engine,
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
from sqlalchemy.orm import sessionmaker, relationship, Session
import requests
import aiohttp

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
DATE_FORMAT = "%Y-%m-%d"

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
    phone_number = Column(String)  # For easy contact on mobile frontend
    thoroughfare = Column(String)
    locality = Column(String)
    state = Column(String)
    postal_code = Column(String)
    full_address = Column(String)
    wwoz_venue_href = Column(String)
    website = Column(String)
    is_active = Column(
        Boolean, default=True
    )  # Added for venue status ie: is it still in business?
    # Geolocation fields
    latitude = Column(Float)  # Latitude of the venue
    longitude = Column(Float)  # Longitude of the venue
    # TODO: OPENAI CAN HANDLE THIS INFO POTENTIALLY; Added for festival planning; attrs not yet available
    capacity = Column(Integer)  # Added for festival planning; attr not yet available
    is_indoor = Column(
        Boolean, default=True
    )  # Added for festival planning; attr not yet available
    last_updated = Column(DateTime(timezone=True), server_default="now()")
    # relational fields
    genres = relationship("Genre", secondary="venue_genres", back_populates="venues")
    events = relationship("Event", back_populates="venue")
    artists = relationship("Artist", secondary="venue_artists", back_populates="venues")

    @hybrid_property
    def full_url(self):
        return urljoin(SAMPLE_WEBSITE, self.wwoz_venue_href)


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    wwoz_artist_href = Column(String)
    description = Column(String)  # TODO: USE OPENAI TO SUMMARIZE? -> Added for potential
    # Experimental fields
    popularity_score = Column(Float)  # Added for festival planning
    typical_set_length = Column(Interval)  # Added for scheduling
    # relational fields
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
    # Added for event details if any; may have price, age, etc
    description = Column(String)  # TODO: Use OPENAI to infer other attrs.
    # SQL Alchemy will set the IDS from the relational fields
    artist_id = Column(Integer, ForeignKey("artists.id"))
    venue_id = Column(Integer, ForeignKey("venues.id"))
    artist_name = Column(String)
    venue_name = Column(String)
    performance_time = Column(DateTime(timezone=True), nullable=False)
    # Added for Gantt charts
    end_time = Column(
        DateTime(timezone=True)
    )  # TODO: SEE IF OPENAI CAN INFER THIS FROM DESCRIPTIONS
    scrape_date = Column(Date, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default="now()")
    # TODO: SCRAPE THESE ATTRS FROM EVENT DETAILS, OR USE OPENAI TO INFER RECURRENCE
    is_recurring = Column(Boolean, default=False)  # Added for recurring events
    recurrence_pattern = Column(String)  # e.g., "weekly", "monthly", "annual"
    # All are indoors unless the venue states otherwise.
    # Example: Bacchanal (OUTDOORS) https://www.wwoz.org/organizations/bacchanal-outdoors
    is_indoors = Column(Boolean)  # Added for Gantt planning
    # relational fields
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

    venues = relationship("Venue", secondary="venue_genres", back_populates="genres")
    artists = relationship(
        "Artist", secondary="artist_genres", back_populates="artists"
    )
    events = relationship("Event", secondary="event_genres", back_populates="genres")


# Join Tables
class ArtistRelation(Base):
    __tablename__ = "artist_relations"

    artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)
    related_artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)

    # Add indexes for better performance
    __table_args__ = (
        Index("ix_artist_relation_artist_id", artist_id),
        Index("ix_artist_relation_related_artist_id", related_artist_id),
    )


class VenueArtist(Base):
    __tablename__ = "venue_artists"

    venue_id = Column(Integer, ForeignKey("venues.id"), primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)

    # Add indexes for better performance
    __table_args__ = (
        Index("ix_venue_artist_venue_id", venue_id),
        Index("ix_venue_artist_artist_id", artist_id),
    )


class VenueEvent(Base):
    __tablename__ = "venue_events"

    venue_id = Column(Integer, ForeignKey("venues.id"), primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), primary_key=True)

    # Add indexes for better performance
    __table_args__ = (
        Index("ix_venue_event_venue_id", venue_id),
        Index("ix_venue_event_event_id", event_id),
    )


class VenueGenre(Base):
    __tablename__ = "venue_genres"

    venue_id = Column(Integer, ForeignKey("venues.id"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id"), primary_key=True)

    # Add indexes for better performance
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

    # Add indexes
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

    # Add indexes
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
    scrape_date: date


def geocode_address(address: str) -> dict:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key}

    response = requests.get(base_url, params=params)
    data = response.json()

    if data["status"] == "OK":
        result = data["results"][0]
        lat = result["geometry"]["location"]["lat"]
        lng = result["geometry"]["location"]["lng"]
        return {"latitude": lat, "longitude": lng}
    else:
        raise ScrapingError(
            message=f"Geocoding failed: {data['status']} - {data.get('error_message')}",
            error_type=ErrorType.GOOGLE_MAPS_API_ERROR,
            status_code=500,
        )


class DatabaseHandler:
    def __init__(self):
        db_url = os.getenv("PG_DATABASE_URL")
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def get_or_create_genre(self, session, name):
        genre = session.query(Genre).filter_by(name=name).first()
        if not genre:
            genre = Genre(name=name)
            session.add(genre)
        return genre

    def save_events(self, events: List[EventDTO], scrape_date: date):
        session = self.Session()
        try:
            for event in events:
                genre_objects = [
                    self.get_or_create_genre(session, genre_name)
                    for genre_name in event.event_data.genres
                ]
                # Get or create venue
                venue = session.query(Venue).filter_by(name=event.venue_data.name).first()
                if not venue:
                    geolocation = geocode_address(event.venue_data.full_address)
                    latitude = geolocation["latitude"]
                    longitude = geolocation["longitude"]
                    venue = Venue(
                        name=event.venue_data.name,
                        phone_number=event.venue_data.phone_number,
                        thoroughfare=event.venue_data.thoroughfare,
                        locality=event.venue_data.locality,
                        state=event.venue_data.state,
                        postal_code=event.venue_data.postal_code,
                        full_address=event.venue_data.full_address,
                        wwoz_venue_url=event.venue_data.wwoz_venue_href,
                        website=event.venue_data.website,
                        is_active=event.venue_data.is_active,
                        latitude=latitude,
                        longitude=longitude,
                        genres=genre_objects,
                    )
                    session.add(venue)

                # Get or create artist
                artist = (
                    session.query(Artist)
                    .filter_by(name=event.artist_data.name)
                    .first()
                )
                if not artist:  # add some data if available
                    artist = Artist(
                        name=event.artist_data.name,
                        wwoz_artist_href=event.artist_data.wwoz_artist_href,
                        related_artists=event.artist_data.related_artists,
                        genres=genre_objects,
                    )
                    session.add(artist)

                # Create event
                new_event = Event(
                    wwoz_event_href=event.event_data.wwoz_event_href,
                    description=event.event_data.description,
                    artist_name=event.artist_data.name,
                    venue_name=event.venue_data.name,
                    performance_time=event.performance_time,
                    scrape_date=scrape_date,
                    artist=artist,
                    venue=venue,
                    genres=genre_objects,
                )
                session.add(new_event)

            session.commit()
        except Exception as e:
            session.rollback()
            raise DatabaseHandlerError(
                message=f"Error saving event data to database: {e}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

        finally:
            session.close()

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
            return urljoin(base_url, endpoint, "?" + urlencode(params))
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
        print("running get artist data")
        if wwoz_artist_href in self.seen_urls:
            return {}

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
        self, wwoz_event_href: str, artist_name: str
    ) -> tuple[EventData, ArtistData]:
        """Deep crawl venue page to get additional details"""
        print("running get event data")
        if wwoz_event_href in self.seen_urls:
            return {}

        # TODO: CLEAN UP EXCESS VARS
        self.seen_urls.add(wwoz_event_href)
        soup = await self.make_soup(wwoz_event_href)

        event_data = EventData(
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
        artist_data = None

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
                # use href to get details, and return the oringal href in the venue data
                # TODO: If venue not in DB, get info about it
                # TODO: else if last updated over 1 month, get updated info
                # TODO: for now, just get the venue details to protoype
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
                        wwoz_event_href, event_artist_name
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
                        scrape_date=datetime.now(NEW_ORLEANS_TZ).date(),
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


def generate_date_str() -> str:
    try:
        date_param = datetime.now(NEW_ORLEANS_TZ).date()
        date_format = os.getenv("DATE_FORMAT", DATE_FORMAT)
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


# TODO: add more validation for the various query string parameters
def validate_params(query_string_params: Dict[str, str] = {}) -> Dict[str, str]:
    # validate the date parameter (only 1 parameter is expected)
    date_param = query_string_params.get("date")
    if date_param:
        try:
            datetime.strptime(date_param, DATE_FORMAT).date()
        except ValueError as e:
            raise ScrapingError(
                message=f"Invalid date format: {e}",
                error_type=ErrorType.VALUE_ERROR,
                status_code=400,
            )
    else:
        date_param = generate_date_str()

    return {**query_string_params, "date": date_param}


async def create_events(aws_info: AwsInfo, event: Dict[str, Any]) -> ResponseType:
    try:
        # validate the parameters
        params = validate_params(event.get("queryStringParameters", {}))
        deep_scraper = DeepScraper()
        print("running DeepScraper")
        events = await deep_scraper.run(params)
        # Save to database
        scrape_date = datetime.strptime(params["date"], DATE_FORMAT).date()
        db_service = DatabaseHandler()
        print("running DatabaseHandler.save_events")
        await db_service.save_events(events, scrape_date)

        # TODO: INTEGRATE WITH AWS TO STORE RAW DATA IN S3 FOR BACK TESTING
        # for now, just return the List of EventDTOs
        return generate_response(
            200,
            {
                "status": "success",
                "data": events,
                "date": params["date"],
                **aws_info,
            },
        )
    except ScrapingError as e:
        logger.error(f"Scraping error: {e.error_type} - {e.message}")
        return generate_response(
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
        return generate_response(
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
        return generate_response(
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
        return generate_response(
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
        return generate_response(
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


# TODO: redis should be used first, then fallback to postgres
def get_events(use_redis: bool = False) -> ResponseType:
    # TODO: Integrate Cache Pipeline
    # Connect to Redis
    if use_redis:
        redis_client = redis.StrictRedis(
            host="redis-host", port=6379, decode_responses=True
        )
        cached_data = redis_client.get("latest_data")

        if cached_data:
            # Return cached data
            return {"statusCode": 200, "body": cached_data}
    else:
        # Fallback to Postgres
        # For PROTOTYPE we will read from db
        db_handler = DatabaseHandler()
        events = db_handler.get_events()

        # Cache the data again
        redis_client.set("latest_data", json.dumps(events))

        return {"statusCode": 200, "body": json.dumps(events)}


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
            return await create_events(aws_info, event)
        elif http_method == "GET":
            return get_events()
        else:
            return generate_response(
                400,
                {
                    "status": "error",
                    "error": "Invalid HTTP method",
                },
            )
    except Exception as e:
        return generate_response(500, {"status": "error", "error": str(e)})
