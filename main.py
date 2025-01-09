import os
import json
import logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import redis
import psycopg2
from botocore.exceptions import ClientError
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime
import pytz
from typing import Dict, Any, List, TypedDict, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional

load_dotenv()  # Load variables from .env
pg_database_url = os.getenv("PG_DATABASE_URL")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define the sample website to scrape
# TODO: scrape from many sites...
SAMPLE_WEBSITE = "https://www.wwoz.org"
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


@dataclass
class Venue:
    name: str
    location: str
    genres: List[str]


@dataclass
class Artist:
    name: str
    genres: List[str]


@dataclass
class Event:
    artist: Artist
    venue: Venue
    performance_time: datetime
    scrape_date: date


class DatabaseHandler:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)

    def close(self):
        self.cursor.close()
        self.conn.close()

    def insert_event(self, event: Event):
        try:
            # First, insert or get venue
            self.cursor.execute(
                """
                INSERT INTO venue (name, location)
                VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET location = EXCLUDED.location
                RETURNING id
            """,
                (event.venue.name, event.venue.location),
            )
            venue_id = self.cursor.fetchone()["id"]

            # Then, insert or get artist
            self.cursor.execute(
                """
                INSERT INTO artist (name)
                VALUES (%s)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            """,
                (event.artist.name,),
            )
            result = self.cursor.fetchone()
            if result:
                artist_id = result["id"]
            else:
                self.cursor.execute(
                    "SELECT id FROM artist WHERE name = %s", (event.artist.name,)
                )
                artist_id = self.cursor.fetchone()["id"]

            # Finally, insert event
            self.cursor.execute(
                """
                INSERT INTO event (artist_id, venue_id, performance_time, scrape_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (artist_id, venue_id, performance_time)
                DO UPDATE SET last_updated = CURRENT_TIMESTAMP
                RETURNING id
            """,
                (artist_id, venue_id, event.performance_time, event.scrape_date),
            )

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise DatabaseError(f"Failed to insert event: {str(e)}")

    def get_events(self, start_date: date, end_date: date) -> List[Dict]:
        self.cursor.execute(
            """
            SELECT
                e.id as event_id,
                e.performance_time,
                a.name as artist_name,
                v.name as venue_name,
                v.location as venue_location
            FROM event e
            JOIN artist a ON e.artist_id = a.id
            JOIN venue v ON e.venue_id = v.id
            WHERE DATE(e.performance_time) BETWEEN %s AND %s
            ORDER BY e.performance_time
        """,
            (start_date, end_date),
        )
        return self.cursor.fetchall()


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


def get_url(
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


def parse_html(html: str) -> List[Event]:
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
            for row in panel.find_all("div", class_="row"):
                calendar_info = row.find("div", class_="calendar-info")
                if not calendar_info:
                    continue

                artist_link = calendar_info.find("a")
                if not artist_link:
                    continue

                # Extract venue info
                venue_div = row.find("div", class_="venue-info")
                venue_name = (
                    venue_div.find("h4").text.strip()
                    if venue_div and venue_div.find("h4")
                    else "Unknown Venue"
                )
                venue_location = (
                    venue_div.find("p").text.strip()
                    if venue_div and venue_div.find("p")
                    else "Unknown Location"
                )

                # Extract time
                time_div = row.find("div", class_="time-info")
                time_str = time_div.text.strip() if time_div else None
                performance_time = parse_time(time_str) if time_str else None

                event = Event(
                    artist=Artist(
                        name=artist_link.text.strip(),
                        genres=[],  # To be populated later
                    ),
                    venue=Venue(
                        name=venue_name,
                        location=venue_location,
                        genres=[],  # To be populated later
                    ),
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


def parse_time(time_str: Optional[str]) -> Optional[datetime]:
    if not time_str:
        return None

    # Implement time parsing logic based on the website's format
    # This is a placeholder - adjust according to actual time format
    try:
        return datetime.strptime(time_str, "%I:%M %p")
    except ValueError:
        return None


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
        url = get_url(params)
        html = fetch_html(url)
        return parse_html(html)
    except ScrapingError:
        raise
    except Exception as e:
        logger.error(f"A {ErrorType.GENERAL_ERROR.value} occurred : {e}")
        raise


def run_scraper(aws_info: AwsInfo, event: Dict[str, Any]) -> ResponseType:
    try:
        # validate the parameters
        params = validate_params(event.get("queryStringParameters", {}))
        events = scrape(params)
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
        conn = psycopg2.connect(pg_database_url)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM my_table")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Cache the data again
        redis_client.set("latest_data", json.dumps(rows))

        return {"statusCode": 200, "body": json.dumps(rows)}


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> ResponseType:
    # record the AWS request ID and log stream name for all responses...
    aws_info = {
        "aws_request_id": context.aws_request_id,
        "log_stream_name": context.log_stream_name,
    }

    mode = event.get("mode", "read")

    if mode == "scraper_write_mode":
        return run_scraper(aws_info, event)
    elif mode == "db_read_mode":
        return read_from_db()
    else:
        return {"statusCode": 400, "body": "Invalid mode"}
