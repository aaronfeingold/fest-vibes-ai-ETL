import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, date
from main import (
    DeepScraper,
    ScrapingError,
    ErrorType,
    VenueData,
    ArtistData,
    EventData,
    EventDTO,
    Utilities,
    Controllers,
)

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


# Test Utility functions first (simple, no async)
def test_generate_response():
    """Test the generate_response function"""
    response = Utilities.generate_response(200, {"status": "success", "data": "test"})

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json"
    assert response["body"]["status"] == "success"
    assert response["body"]["data"] == "test"


def test_validate_params():
    """Test the validate_params function"""
    # Test with valid date
    params = {"date": "2025-03-21"}
    result = Utilities.validate_params(params)
    assert result["date"] == "2025-03-21"

    # Test with missing date (should generate one)
    params = {}
    result = Utilities.validate_params(params)
    assert "date" in result
    assert len(result["date"]) == 10  # YYYY-MM-DD format


# Test basic scraper methods with mocked responses
@pytest.mark.asyncio
async def test_generate_url():
    """Test the generate_url method"""
    scraper = DeepScraper()
    url = scraper.generate_url({"date": "2025-03-21"})
    assert "date=2025-03-21" in url


@pytest.mark.asyncio
async def test_fetch_html_success():
    scraper = DeepScraper()

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

        def __await__(self):
            async def dummy():
                return self
            return dummy().__await__()


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
    scraper = DeepScraper()

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

        def __await__(self):
            async def dummy():
                return self
            return dummy().__await__()

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
    """Test parsing event performance time"""
    scraper = DeepScraper()

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
    """Test creating EventDTO objects"""
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
    """Test parsing HTML with simplified mocking"""
    scraper = DeepScraper()

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

    # Mock the deeper scrape methods to return simple objects
    scraper.get_venue_data = AsyncMock(
        return_value=VenueData(
            name="Test Venue",
            thoroughfare="123 Test St",
            locality="New Orleans",
            state="LA",
            postal_code="70116"
        )
    )

    event_data = EventData(
        event_date=datetime.now().date(),
        event_artist="Test Artist",
        wwoz_event_href="/events/456",
        description="Test description"
    )

    artist_data = ArtistData(
        name="Test Artist",
        genres=["Jazz", "Blues"],
        wwoz_artist_href="/artists/789"
    )

    scraper.get_event_data = AsyncMock(return_value=(event_data, artist_data))

    # Test the parser with the simplified HTML
    events = await scraper.parse_html(html, "2025-03-21")

    assert len(events) == 1
    assert events[0].venue_data.name == "Test Venue"
    assert events[0].artist_data.name == "Test Artist"
    assert events[0].event_data.event_artist == "Test Artist"

    # Verify the mock methods were called
    scraper.get_venue_data.assert_called_once()
    scraper.get_event_data.assert_called_once()


@pytest.mark.asyncio
async def test_create_events_controller():
    """Test the create_events controller function"""
    # Mock dependencies
    event = {"queryStringParameters": {"date": "2025-03-21"}}
    aws_info = {"aws_request_id": "test-id", "log_stream_name": "test-stream"}

    # Create a mock event list to return
    events = [
        EventDTO(
            venue_data=VenueData(name="Test Venue"),
            artist_data=ArtistData(name="Test Artist"),
            event_data=EventData(
                event_date=datetime.now().date(),
                event_artist="Test Artist"
            ),
            performance_time=datetime.now(),
            scrape_time=date.today()
        )
    ]

    # Mock DeepScraper and FileHandler
    with patch("main.DeepScraper") as MockScraper, \
         patch("main.DatabaseHandler.create") as MockDbHandler, \
         patch("main.FileHandler.save_events_local") as MockSaveEvents:

        # Setup mocks
        scraper_instance = MockScraper.return_value
        scraper_instance.run = AsyncMock(return_value=events)

        db_handler = AsyncMock()
        MockDbHandler.return_value = db_handler
        db_handler.save_events = AsyncMock()
        db_handler.close = AsyncMock()

        MockSaveEvents.return_value = "path/to/file.json"

        # Call the controller
        response = await Controllers.create_events(aws_info, event, dev_env=False)

        # Verify response
        assert response["statusCode"] == 200
        assert response["body"]["status"] == "success"
        assert "data" in response["body"]
        assert "aws_request_id" in response["body"]

        # Verify mocks were called
        scraper_instance.run.assert_called_once()
        MockSaveEvents.assert_called_once()
        db_handler.save_events.assert_called_once()
        db_handler.close.assert_called_once()
