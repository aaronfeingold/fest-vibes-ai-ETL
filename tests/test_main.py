import pytest
from unittest.mock import patch, Mock
from datetime import datetime
from main import lambda_handler, scrape

# Sample HTML content for testing
SAMPLE_HTML = """
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
            </div>
        </div>
    </body>
</html>
"""


@pytest.fixture
def mock_urlopen():
    mock_response = Mock()
    mock_response.read.return_value = SAMPLE_HTML.encode("utf-8")

    mock_urlopen = Mock()
    mock_urlopen.return_value = mock_response
    mock_urlopen.__enter__.return_value = mock_response
    mock_urlopen.__exit__.return_value = False

    with patch("main.urlopen", mock_urlopen):
        yield mock_urlopen


@pytest.fixture
def mock_date():
    with patch("main.datetime") as mock_datetime:
        mock_date = Mock(wraps=datetime(2024, 9, 17))
        mock_datetime.now.return_value = mock_date
        mock_date.date.return_value = mock_date
        mock_date.strftime.return_value = "2024-09-17"
        yield mock_date


@pytest.fixture
def mock_fetch_html():
    with patch("main.fetch_html") as mock:
        mock.return_value = SAMPLE_HTML
        yield mock


@pytest.fixture
def mock_parse_html():
    with patch("main.parse_html") as mock:
        mock.return_value = [{"Artist 1": "/events/1234"}, {"Artist 2": "/events/5678"}]
        yield mock


def test_scrape_success(mock_urlopen):
    mock_urlopen.return_value.read.return_value = SAMPLE_HTML.encode("utf-8")

    result = lambda_handler(None, None)

    expected = [{"Artist 1": "/events/1234"}, {"Artist 2": "/events/5678"}]
    assert result == expected


def test_scrape_no_livewire_listing(mock_urlopen):
    no_listing_html = "<html><body><div>No Data</div></body></html>"
    mock_urlopen.return_value.read.return_value = no_listing_html.encode("utf-8")

    result = lambda_handler(None, None)

    assert result == []


def test_scrape_empty_response(mock_urlopen):
    mock_urlopen.return_value.read.return_value = b""

    result = lambda_handler(None, None)

    assert result == []


def test_url_formation(mock_urlopen, mock_date):
    mock_urlopen.return_value.read.return_value = SAMPLE_HTML.encode("utf-8")

    # ensure it returns the default values as specified in the scrape function
    with patch("os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda key, default: default
        scrape()

    expected_url = "https://www.wwoz.org/calendar/livewire-music?date=2024-09-17"
    mock_urlopen.assert_called_once()
    actual_url = mock_urlopen.call_args[0][0].full_url
    assert (
        actual_url == expected_url
    ), f"Expected URL: {expected_url}, but got: {actual_url}"

    # Verify that the correct date formatting method was called
    mock_date.date.return_value.strftime.assert_called_once_with("%Y-%m-%d")
