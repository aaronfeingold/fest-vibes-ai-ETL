import pytest
import requests_mock
from main import lambda_handler  # Replace with the actual import path

# Example HTML content for testing
sample_html = """
<html>
    <body>
        <div class="livewire-listing">
            <div class="panel panel-default">
                <div class="row">
                    <div class="calendar-info">
                        <a href="http://example.com/artist1">Artist 1</a>
                    </div>
                </div>
            </div>
        </div>
    </body>
</html>
"""


def test_scrape_success():
    with requests_mock.Mocker() as m:
        m.get(
            "https://www.wwoz.org/calendar/livewire-music?date=2024-09-17",
            text=sample_html,
        )
        result = lambda_handler(None, None)
        expected = [{"Artist 1": "http://example.com/artist1"}]
        assert result == expected


def test_scrape_no_livewire_listing():
    no_listing_html = """
    <html><body><div>No Data</div></body></html>
    """
    with requests_mock.Mocker() as m:
        m.get(
            "https://www.wwoz.org/calendar/livewire-music?date=2024-09-17",
            text=no_listing_html,
        )
        result = lambda_handler(None, None)
        assert result == []


def test_scrape_empty_response():
    with requests_mock.Mocker() as m:
        m.get("https://www.wwoz.org/calendar/livewire-music?date=2024-09-17", text="")
        result = lambda_handler(None, None)
        assert result == []
