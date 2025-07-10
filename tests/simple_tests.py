from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

from ETL.extractor.service import ScraperService
from ETL.shared.schemas import ArtistData, EventData, EventDTO, VenueData
from ETL.shared.utils.errors import ScrapingError
from ETL.shared.utils.types import ErrorType

# Test data
MOCK_HTML = """
<html>
<body>
    <div class="livewire-listing">
        <div class="panel panel-default">
            <h3 class="panel-title"><a href="/venues/123">Test Venue</a></h3>
            <div class="panel-body">
                <div class="row">
                    <div class="calendar-info">
                        <a href="/events/456">Test Artist</a>
                        <p>Genre</p>
                        <p>8:00pm</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""


# Test basic scraper methods with mocked responses
@pytest.mark.asyncio
async def test_fetch_html_success():
    """Test successful HTML fetching."""
    scraper = ScraperService()

    class MockResponse:
        def __init__(self, text, status=200):
            self._text = text
            self.status = status

        async def text(self):
            return self._text

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def get(self, url, **kwargs):
            return MockResponse(MOCK_HTML, status=200)

        async def close(self):
            pass

    scraper.session = MockSession()
    html = await scraper.fetch_html("https://example.com")
    assert html == MOCK_HTML


@pytest.mark.asyncio
async def test_fetch_html_failure():
    """Test HTML fetching failure."""
    scraper = ScraperService()

    class MockResponse:
        def __init__(self, text, status=404):
            self._text = text
            self.status = status

        async def text(self):
            return self._text

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def get(self, url, **kwargs):
            return MockResponse("", status=404)

        async def close(self):
            pass

    scraper.session = MockSession()

    with pytest.raises(ScrapingError) as excinfo:
        await scraper.fetch_html("https://example.com")

    assert excinfo.value.error_type == ErrorType.HTTP_ERROR


@pytest.mark.asyncio
async def test_parse_event_performance_time():
    """Test parsing event performance time."""
    scraper = ScraperService()

    # Test valid time
    date_str = "2025-03-21"
    time_str = "8:00pm"

    result = scraper.parse_event_performance_time(date_str, time_str)
    assert result.hour == 20
    assert result.minute == 0

    # Test time with whitespace
    time_str = "  9:30am  "
    result = scraper.parse_event_performance_time(date_str, time_str)
    assert result.hour == 9
    assert result.minute == 30


# Test data structures
def test_event_dto_creation():
    """Test creating EventDTO objects."""
    venue = VenueData(name="Test Venue", thoroughfare="123 Test St")
    artist = ArtistData(name="Test Artist", genres=["Jazz", "Blues"])
    event_date = datetime.now().date()
    event = EventData(
        event_date=event_date,
        event_artist="Test Artist",
        wwoz_event_href="/events/123",
    )

    performance_time = datetime.now()
    scrape_time = date.today()

    event_dto = EventDTO(
        venue_data=venue,
        artist_data=artist,
        event_data=event,
        performance_time=performance_time,
        scrape_time=scrape_time,
    )

    assert event_dto.venue_data.name == "Test Venue"
    assert event_dto.artist_data.name == "Test Artist"
    assert event_dto.event_data.event_artist == "Test Artist"
    assert event_dto.performance_time == performance_time
    assert event_dto.scrape_time == scrape_time


# Integration tests with more thorough mocking
@pytest.mark.asyncio
async def test_simplified_parse_html():
    """Test parsing HTML with simplified mocking."""
    scraper = ScraperService()

    # Sample HTML with minimum structure needed
    html = """
    <div class="livewire-listing">
        <div class="panel panel-default">
            <h3 class="panel-title"><a href="/venues/123">Test Venue</a></h3>
            <div class="panel-body">
                <div class="row">
                    <div class="calendar-info">
                        <a href="/events/456">Test Artist</a>
                        <p>Genre</p>
                        <p>8:00pm</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    # Create BeautifulSoup object from HTML
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Mock the deeper scrape methods to return simple objects
    scraper.get_venue_data = AsyncMock(
        return_value=VenueData(
            name="Test Venue",
            thoroughfare="123 Test St",
            locality="New Orleans",
            state="LA",
            postal_code="70116",
        )
    )

    event_data = EventData(
        event_date=datetime.now().date(),
        event_artist="Test Artist",
        wwoz_event_href="/events/456",
        description="Test description",
    )

    artist_data = ArtistData(
        name="Test Artist", genres=["Jazz", "Blues"], wwoz_artist_href="/artists/789"
    )

    scraper.get_event_data = AsyncMock(return_value=(event_data, artist_data))

    # Test the parser with the simplified HTML
    events = await scraper.parse_base_html(soup, "2025-03-21")

    assert len(events) == 1
    assert events[0].venue_data.name == "Test Venue"
    assert events[0].artist_data.name == "Test Artist"
    assert events[0].event_data.event_artist == "Test Artist"

    # Verify the mock methods were called
    scraper.get_venue_data.assert_called_once()
    scraper.get_event_data.assert_called_once()


@pytest.mark.asyncio
async def test_scraper_service_run():
    """Test the main scraper service run method."""
    scraper = ScraperService()

    # Mock the make_soup method to return a simple soup
    from bs4 import BeautifulSoup

    mock_soup = BeautifulSoup(MOCK_HTML, "html.parser")
    scraper.make_soup = AsyncMock(return_value=mock_soup)

    # Mock the parse_base_html method
    venue = VenueData(name="Test Venue")
    artist = ArtistData(name="Test Artist")
    event = EventData(
        event_date=datetime.now().date(),
        event_artist="Test Artist",
        wwoz_event_href="/events/456",
    )

    event_dto = EventDTO(
        venue_data=venue,
        artist_data=artist,
        event_data=event,
        performance_time=datetime.now(),
        scrape_time=date.today(),
    )

    scraper.parse_base_html = AsyncMock(return_value=[event_dto])

    # Test the run method
    params = {"date": "2025-03-21"}
    events = await scraper.run(params)

    assert len(events) == 1
    assert events[0].venue_data.name == "Test Venue"
    assert events[0].artist_data.name == "Test Artist"

    # Verify the mock methods were called
    scraper.make_soup.assert_called_once()
    scraper.parse_base_html.assert_called_once()


@pytest.mark.asyncio
async def test_get_text_or_default():
    """Test the get_text_or_default utility method."""
    scraper = ScraperService()
    from bs4 import BeautifulSoup

    html = '<div class="test">Hello World</div>'
    soup = BeautifulSoup(html, "html.parser")

    # Test finding existing element
    result = scraper.get_text_or_default(soup, "div", "test")
    assert result == "Hello World"

    # Test finding non-existent element
    result = scraper.get_text_or_default(soup, "div", "nonexistent", "default")
    assert result == "default"

    # Test with empty element
    result = scraper.get_text_or_default(soup, "div", "test", "default")
    assert result == "Hello World"


@pytest.mark.asyncio
async def test_is_attribute_non_empty():
    """Test the is_attribute_non_empty utility method."""
    scraper = ScraperService()

    # Test with non-empty attribute
    test_obj = type("TestObj", (), {"name": "Test"})()
    assert scraper.is_attribute_non_empty(test_obj, "name") is True

    # Test with empty attribute
    test_obj = type("TestObj", (), {"name": ""})()
    assert scraper.is_attribute_non_empty(test_obj, "name") is False

    # Test with missing attribute
    test_obj = type("TestObj", (), {})()
    assert scraper.is_attribute_non_empty(test_obj, "name") is False
