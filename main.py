import os
import re
import json
import logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import redis
from botocore.exceptions import ClientError
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin
from datetime import datetime, date
import pytz
from typing import Dict, Any, List, TypedDict, Union, Optional
from enum import Enum
from dataclasses import dataclass
from sqlalchemy import (
    create_engine,
    Boolean,
    Column,
    Integer,
    String,
    DateTime,
    Date,
    ARRAY,
    ForeignKey,
    Float,
    Interval,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import sessionmaker, relationship, Session
import requests

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
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    AWS_ERROR = "AWS_ERROR"
    VALUE_ERROR = "VALUE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    GOOGLE_MAPS_API_ERROR = "GOOGLE_MAPS_API_ERROR"


class ScrapingError(Exception):
    """Custom exception for scraping errors"""

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


Base = declarative_base()


# Database Models
class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    # Geolocation fields
    latitude = Column(Float)  # Latitude of the venue
    longitude = Column(Float)  # Longitude of the venue
    wwoz_venue_href = Column(String)
    capacity = Column(Integer)  # Added for festival planning; attr not yet available
    indoor = Column(Boolean)  # Added for festival planning; attr not yet available

    genres = relationship("Genre", secondary="venue_genres", back_populates="venues")
    events = relationship("Event", back_populates="venue")
    artists = relationship("Artist", secondary="venue_artists")

    @hybrid_property
    def full_url(self):
        return urljoin(SAMPLE_WEBSITE, self.wwoz_venue_href)


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    popularity_score = Column(Float)  # Added for festival planning
    typical_set_length = Column(Interval)  # Added for scheduling
    events = relationship("Event", back_populates="artist")
    venues = relationship("Venue", secondary="venue_artists")
    genres = relationship("Genre", secondary="artist_genres", back_populates="artists")
    related_artists = relationship(
        "Artist",
        secondary="artist_relations",
        primaryjoin="Artist.id==ArtistRelation.artist_id",
        secondaryjoin="Artist.id==ArtistRelation.related_artist_id",
    )


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id"))
    venue_id = Column(Integer, ForeignKey("venues.id"))
    performance_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))  # Added for Gantt charts
    scrape_date = Column(Date, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default="now()")
    wwoz_event_href = Column(String)
    is_recurring = Column(Boolean, default=False)  # Added for recurring events
    recurrence_pattern = Column(String)  # e.g., "weekly", "monthly", "annual"
    is_indoors = Column(Boolean)  # Added for Gantt planning
    artist = relationship("Artist", back_populates="events")
    venue = relationship("Venue", back_populates="events")

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

# Join Tables
class ArtistRelation(Base):
    __tablename__ = "artist_relations"

    artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)
    related_artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)


class VenueArtist(Base):
    __tablename__ = "venue_artists"

    venue_id = Column(Integer, ForeignKey("venues.id"), primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), primary_key=True)


class VenueEvent(Base):
    __tablename__ = "venue_events"

    venue_id = Column(Integer, ForeignKey("venues.id"), primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), primary_key=True)


class VenueGenre(Base):
    __tablename__ = "venue_genres"

    venue_id = Column(Integer, ForeignKey("venues.id"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id"), primary_key=True)


class ArtistGenre(Base):
    __tablename__ = "artist_genres"

    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = Column(
        Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )


# Data Transfer Objects
@dataclass
class EventDTO:
    artist_name: str
    venue_name: str
    venue_location: str
    performance_time: datetime
    artist_url: str
    venue_url: Optional[str] = None


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

    def save_events(self, events: List[Event], scrape_date: date):
        session = self.Session()
        try:
            for event in events:
                # Get or create venue
                venue = session.query(Venue).filter_by(name=event.venue.name).first()
                if not venue:
                    geolocation = geocode_address(event.venue_location)
                    latitude = geolocation["latitude"]
                    longitude = geolocation["longitude"]
                    venue = Venue(
                        name=event.venue_name,
                        location=event.venue_location,
                        wwoz_venue_url=event.venue_url,
                        latitude=latitude,
                        longitude=longitude,
                    )
                    session.add(venue)

                # Get or create artist
                artist = (
                    session.query(Artist)
                    .filter_by(name=event.artist.artist_name)
                    .first()
                )
                if not artist:
                    artist = Artist(name=event.artist.artist_name)
                    session.add(artist)

                # Create event
                new_event = Event(
                    artist=artist,
                    venue=venue,
                    performance_time=event.performance_time,
                    scrape_date=scrape_date,
                    wwoz_event_href=event.wwoz_event_href,
                )
                session.add(new_event)

            session.commit()
        except Exception as e:
            session.rollback()
            raise ScrapingError(
                message=f"An unexpected error occurred while inserting: {e}",
                error_type=ErrorType.DATABASE_ERROR,
                status_code=500,
            )

        finally:
            session.close()

    def get_events_in_date_range(
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
        events = (
            session.query(Event)
            .filter(
                Event.performance_time >= start_date, Event.performance_time <= end_date
            )
            .all()
        )

        return events


def generate_url(
    params: Dict[str, str] = {},
    base_url: str = SAMPLE_WEBSITE,
    endpoint: str = SAMPLE_ENDPOINT,
) -> str:
    params_str = ""
    if params:
        params_str = "&".join([f"?{k}={v}" for k, v in params.items()])
    try:
        return f"{base_url}{endpoint}{params_str}"
    except (TypeError, Exception) as e:
        raise ScrapingError(
            message=f"Failed to create URL: {e}",
            error_type=ErrorType.GENERAL_ERROR,
            status_code=500,
        )


def fetch_html(url: str) -> str:
    try:
        req = Request(url, headers=DEFAULT_HEADERS)
        with urlopen(req) as response:
            return response.read().decode("utf-8")
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


def parse_html(html: str, date_str: str) -> List[Event]:
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
            if not panel_title:
                logger.warning("Panel is missing Venue Name...This is unexpected.")
            # strip text to get venue name
            venue_name = (
                panel_title.find("a").text.strip() if panel_title else "Unknown Venue"
            )
            # get wwoz's venue href from the venue name
            # TODO: use href to scrape more data
            wwoz_venue_href = panel_title.find("a")["href"]
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
                artist_name = wwoz_event_link.text.strip()
                wwoz_event_href = wwoz_event_link["href"]
                # Extract time
                time_str = calendar_info.find_all("p")[1].text.strip()
                performance_time = (
                    parse_datetime(date_str, time_str) if time_str else None
                )

                event = Event(
                    artist=Artist(
                        name=artist_name,
                        genres=[],  # To be populated later
                    ),
                    venue=Venue(
                        name=venue_name,
                        wwoz_venue_href=wwoz_venue_href,
                        genres=[],  # To be populated later
                    ),
                    wwoz_event_href=wwoz_event_href,
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


def parse_datetime(date_str: str, time_str: str) -> datetime:
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


def create_response(status_code: int, body: ResponseBody) -> ResponseType:
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


def scrape(params: Dict[str, str]) -> list | List[Dict[str, str]]:
    try:
        html = fetch_html(generate_url(params))
        return parse_html(html, params["date"])
    except ScrapingError:
        raise
    except Exception as e:
        logger.error(f"A {ErrorType.GENERAL_ERROR.value} occurred : {e}")
        raise


def run_scraper(aws_info: AwsInfo, event: Dict[str, Any]) -> ResponseType:
    db_service = DatabaseHandler()
    try:
        # validate the parameters
        params = validate_params(event.get("queryStringParameters", {}))
        events = scrape(params)
        # Save to database
        scrape_date = datetime.strptime(params["date"], DATE_FORMAT).date()
        db_service.save_events(events, scrape_date)

        return create_response(
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
        return create_response(
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
        return create_response(
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
        return create_response(
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
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return create_response(
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


# TODO: should return a ResponseType
def read_from_db():
    # Connect to Redis
    redis_client = redis.StrictRedis(
        host="redis-host", port=6379, decode_responses=True
    )
    cached_data = redis_client.get("latest_data")

    if cached_data:
        # Return cached data
        return {"statusCode": 200, "body": cached_data}
    else:
        # Fallback to Postgres
        db_handler = DatabaseHandler()
        events = db_handler.get_events_in_date_range()

        # Cache the data again
        redis_client.set("latest_data", json.dumps(events))

        return {"statusCode": 200, "body": json.dumps(events)}


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> ResponseType:
    # record the AWS request ID and log stream name for all responses...
    aws_info = {
        "aws_request_id": context.aws_request_id,
        "log_stream_name": context.log_stream_name,
    }
    # POST and GET To AWS API Gateway only; reuses the same image
    http_method = event.get("httpMethod", "GET")
    try:
        if http_method == "POST":
            return run_scraper(aws_info, event)
        elif http_method == "GET":
            return read_from_db()
        else:
            return create_response(
                400,
                {
                    "status": "error",
                    "error": "Invalid HTTP method",
                },
            )
    except Exception as e:
        return create_response(500, {"status": "error", "error": str(e)})
