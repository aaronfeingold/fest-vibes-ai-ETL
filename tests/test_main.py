import pytest
from unittest.mock import patch, Mock, MagicMock
from urllib.error import HTTPError
from datetime import datetime, timedelta
from main import (
    lambda_handler,
    scrape,
    get_url,
    ScrapingError,
    ErrorType,
    SAMPLE_WEBSITE,
    DATE_FORMAT,
)

SAMPLE_HTML = f"""
<html>
    <body>
        <div class="livewire-listing">
            <div class="panel panel-default">
                <div class="row">
                    <div class="calendar-info">
                        <a href="/events/1234">Artist 1</a>
                    </div>
                </div>
                <div class="row">
                    <div class="calendar-info">
                        <a href="/events/5678">Artist 2</a>
                    </div>
                </div>
                <div class="row">
                    <div class="calendar-info">
                        <a href="{SAMPLE_WEBSITE}/events/9012">Artist 3</a>
                    </div>
                </div>
            </div>
        </div>
    </body>
</html>
"""

NO_LISTING_HTML = "<html><body><div>No Data</div></body></html>"

today = datetime.today()
TODAY_FORMATTED = today.strftime(DATE_FORMAT)
yesterday = today - timedelta(days=1)
MOCK_DATE = yesterday.strftime(DATE_FORMAT)


@pytest.fixture
def mock_aws_context():
    context = Mock()
    context.aws_request_id = "test-request-id"
    context.log_stream_name = "test-log-stream"
    return context


@pytest.fixture
def mock_default_event():
    return {"queryStringParameters": {}}


@pytest.fixture
def mock_urlopen():
    with patch("main.urlopen") as mock:
        mock_cm = MagicMock()
        mock_cm.read.return_value = SAMPLE_HTML.encode("utf-8")
        mock.return_value.__enter__.return_value = mock_cm
        yield mock


@pytest.fixture
def mock_fetch_html():
    with patch("main.fetch_html") as mock:
        mock.return_value = SAMPLE_HTML
        yield mock


def test_lambda_handler_success(mock_urlopen, mock_aws_context):
    # Create a mock event with a valid date query parameter
    event = {"queryStringParameters": {"date": MOCK_DATE}}

    result = lambda_handler(event, mock_aws_context)

    assert result["statusCode"] == 200
    body = result["body"]
    assert body["status"] == "success"
    assert body["date"] == MOCK_DATE
    assert len(body["data"]) == 3
    assert body["data"][0] == {"Artist 1": f"{SAMPLE_WEBSITE}/events/1234"}
    assert body["data"][1] == {"Artist 2": f"{SAMPLE_WEBSITE}/events/5678"}
    assert body["data"][2] == {"Artist 3": f"{SAMPLE_WEBSITE}/events/9012"}
    assert body["aws_request_id"] == "test-request-id"
    assert body["log_stream_name"] == "test-log-stream"


def test_lambda_handler_success_with_no_query_string_params(
    mock_urlopen, mock_aws_context, mock_default_event
):

    result = lambda_handler(mock_default_event, mock_aws_context)

    assert result["statusCode"] == 200
    body = result["body"]
    assert body["date"] == TODAY_FORMATTED


def test_lambda_handler_invalid_date_format(mock_urlopen, mock_aws_context):
    # Create a mock event with an invalid date format
    event = {
        "queryStringParameters": {"date": yesterday.strftime("%m-%d-%Y")}
    }  # Incorrect format

    result = lambda_handler(event, mock_aws_context)

    # Assert the response structure and content
    assert result["statusCode"] == 400
    body = result["body"]
    assert body["status"] == "error"
    assert body["error"]["message"].startswith("Invalid date format")
    assert body["error"]["type"] == ErrorType.VALUE_ERROR.value
    assert body["aws_request_id"] == "test-request-id"
    assert body["log_stream_name"] == "test-log-stream"


def test_lambda_handler_no_events(mock_urlopen, mock_aws_context, mock_default_event):
    mock_urlopen.return_value.__enter__.return_value.read.return_value = (
        NO_LISTING_HTML.encode("utf-8")
    )

    result = lambda_handler(mock_default_event, mock_aws_context)

    assert result["statusCode"] == 404
    body = result["body"]
    assert body["status"] == "error"
    assert body["error"]["type"] == "NO_EVENTS"
    assert "No livewire-listing events found for this date" in body["error"]["message"]


def test_lambda_handler_http_error(mock_urlopen, mock_aws_context, mock_default_event):
    mock_urlopen.side_effect = HTTPError("http://test.com", 404, "Not Found", {}, None)

    result = lambda_handler(mock_default_event, mock_aws_context)

    assert result["statusCode"] == 404
    body = result["body"]
    assert body["status"] == "error"
    assert body["error"]["type"] == "HTTP_ERROR"
    assert "Failed to fetch data: HTTP 404" in body["error"]["message"]


def test_scrape_empty_response(mock_urlopen, mock_aws_context, mock_default_event):
    mock_urlopen.return_value.__enter__.return_value.read.return_value = b""

    result = lambda_handler(mock_default_event, mock_aws_context)

    assert result["statusCode"] == 404
    body = result["body"]
    assert body["status"] == "error"
    assert body["error"]["type"] == "NO_EVENTS"
    assert "No livewire-listing events found" in body["error"]["message"]


def test_scrape_function_empty_response(mock_urlopen):
    mock_urlopen.return_value.__enter__.return_value.read.return_value = b""

    with pytest.raises(ScrapingError) as exc_info:
        scrape()

    assert exc_info.value.error_type == ErrorType.NO_EVENTS
    assert exc_info.value.status_code == 404
    assert "No livewire-listing events found" in str(exc_info.value)


def test_get_url():
    # Call the function with the mock date
    actual_url = get_url()
    EXPECTED_URL = f"{SAMPLE_WEBSITE}/calendar/livewire-music"

    # Assert that the actual URL matches the expected URL
    assert (
        actual_url == EXPECTED_URL
    ), f"Expected URL: {EXPECTED_URL}, but got: {actual_url}"


def test_get_url_params():
    # Call the function with the mock date
    actual_url = get_url({"date": MOCK_DATE})
    EXPECTED_URL = f"{SAMPLE_WEBSITE}/calendar/livewire-music?date={MOCK_DATE}"

    # Assert that the actual URL matches the expected URL
    assert (
        actual_url == EXPECTED_URL
    ), f"Expected URL: {EXPECTED_URL}, but got: {actual_url}"
