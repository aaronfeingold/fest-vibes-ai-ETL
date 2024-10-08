import os
import logging
from bs4 import BeautifulSoup
from botocore.exceptions import ClientError
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime, date
import pytz
from typing import Dict, Any, List, TypedDict, Union
from enum import Enum

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


def parse_html(html: str) -> List[Dict[str, str]]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        livewire_listing = soup.find("div", class_="livewire-listing")
        if not livewire_listing:
            logger.warning("No livewire-listing found on the page.")
            raise ScrapingError(
                message="No livewire-listing events found for this date",
                error_type=ErrorType.NO_EVENTS,
                status_code=404,
            )

        for panel in livewire_listing.find_all("div", class_="panel panel-default"):
            for row in panel.find_all("div", class_="row"):
                artist_link = row.find("div", class_="calendar-info").find("a")
                if artist_link:
                    href = artist_link["href"]
                    full_href = (
                        href if SAMPLE_WEBSITE in href else f"{SAMPLE_WEBSITE}{href}"
                    )
                    links.append({artist_link.text.strip(): full_href})
        return links
    except ScrapingError:
        raise
    except Exception as e:
        raise ScrapingError(
            message=f"Failed to parse webpage content: {e}",
            error_type=ErrorType.PARSE_ERROR,
            status_code=500,
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


def scrape(date: date = str) -> list | List[Dict[str, str]]:
    try:
        url = get_url({"date": date})
        html = fetch_html(url)
        return parse_html(html)
    except ScrapingError:
        raise
    except Exception as e:
        logger.error(f"Error occurred during scraping: {e}")
        raise


def generate_date() -> date:
    try:
        date = datetime.now(NEW_ORLEANS_TZ).date()
        date_format = os.getenv("DATE_FORMAT", DATE_FORMAT)
        return date.strftime(date_format)
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


def validate_params(query_string_params: Dict[str, str] = {}) -> None | str:
    # validate the date parameter (only 1 parameter is expected)
    date = query_string_params.get("date")
    if date:
        try:
            datetime.strptime(date, DATE_FORMAT).date()
        except ValueError as e:
            raise ScrapingError(
                message=f"Invalid date format: {e}",
                error_type=ErrorType.VALUE_ERROR,
                status_code=400,
            )
    else:
        date = generate_date()

    return {**query_string_params, "date": date}


def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> ResponseType:
    # record the AWS request ID and log stream name for all responses...
    aws_info = {
        "aws_request_id": context.aws_request_id,
        "log_stream_name": context.log_stream_name,
    }
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
