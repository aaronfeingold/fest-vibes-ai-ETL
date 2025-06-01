"""
Data Transfer Objects (DTOs) for the application.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

from ajf_live_re_wire_ETL.shared.utils.errors import ErrorType, ValidationError
from ajf_live_re_wire_ETL.shared.utils.logger import logger


@dataclass
class VenueData:
    """
    VenueData is a class that represents information about a venue.

    Attributes:
        name (str): The name of the venue.
        thoroughfare (str): The street address or thoroughfare of the venue.
        phone_number (str): The contact phone number for the venue.
        locality (str): The city or locality where the venue is located. Defaults to "New Orleans".
        state (str): The state where the venue is located.
        postal_code (str): The postal or ZIP code of the venue.
        full_address (str): The complete address of the venue.
        is_active (Boolean): Indicates whether the venue is currently active. Defaults to True.
        website (str): The website URL of the venue.
        wwoz_venue_href (str): A reference link to the venue on the WWOZ website.
        event_artist (str): The artist or performer associated with an event at the venue.
    """

    name: str = ""
    thoroughfare: str = ""
    phone_number: str = ""
    locality: str = "New Orleans"  # Today, local. Tomorrow, the world
    state: str = ""
    postal_code: str = ""
    full_address: str = ""
    is_active: bool = True
    website: str = ""
    wwoz_venue_href: str = ""
    event_artist: str = ""


@dataclass
class ArtistData:
    """
    A class to represent artist data.

    Attributes:
        name (str): The name of the artist.
        description (str): A brief description of the artist. Defaults to "lorum ipsum".
        genres (List[str]): A list of genres associated with the artist.
        related_artists (List[str]): A list of related artists.
        wwoz_artist_href (str): A hyperlink reference to the artist's WWOZ page.
    """

    name: str = ""
    description: str = "lorum ipsum"  # TODO: USE OPENAI TO SUMMARIZE and EXTRACT
    genres: List[str] = field(default_factory=list)
    related_artists: List[str] = field(default_factory=list)
    wwoz_artist_href: str = ""
    website: str = ""


@dataclass
class EventData:
    """
    Represents event data with details about the event, artist, and related information.

    Attributes:
        event_date (datetime): The date of the event.
        wwoz_event_href (str): The hyperlink to the event on WWOZ. Defaults to an empty string.
        event_artist (str): The name of the artist performing at the event.
          Defaults to an empty string.
        wwoz_artist_href (str): The hyperlink to the artist on WWOZ. Defaults to an empty string.
        description (str): A description of the event. Defaults to an empty string.
        related_artists (List[str]): A list of related artists. Defaults to an empty list.
        genres (List[str]): A list of genres associated with the event.
          Defaults to an empty list.
    """

    event_date: datetime
    wwoz_event_href: str = ""
    event_artist: str = ""
    wwoz_artist_href: str = ""
    description: str = ""
    related_artists: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)


@dataclass
class EventDTO:
    """
    Data Transfer Object (DTO) representing an event in the system.

    This DTO serves as a standardized format for transferring event data between different
    layers of the application (database, cache, API). It encapsulates all relevant information
    about an event, including details about the artist, venue, and the event itself.

    The DTO is designed to be:
    - Serializable to JSON for caching and API responses
    - Type-safe through Python's type hints
    - Self-contained with all necessary event information
    - Consistent across the application

    Note on Implementation:
    We use a custom to_dict() method instead of a serialization library like Pydantic
    to maintain container leanness. While Pydantic would provide cleaner code and
    automatic serialization, it would require adding another dependency to our containers.
    This implementation prioritizes minimal dependencies over code elegance, keeping
    our containers lightweight and focused on their specific responsibilities.

    Attributes:
        artist_data (ArtistData): Information about the artist performing at the event,
            including name, description, genres, and related artists.
        venue_data (VenueData): Details about the venue hosting the event, including
            location, contact information, and status.
        event_data (EventData): Core event information such as date, description,
            and associated genres.
        performance_time (datetime): The exact date and time when the event is scheduled
            to occur, including timezone information.
        scrape_time (date): The date when this event data was last scraped or updated
            from the source.

    Example:
        ```python
        event = EventDTO(
            artist_data=ArtistData(name="Artist Name"),
            venue_data=VenueData(name="Venue Name"),
            event_data=EventData(event_date=datetime.now()),
            performance_time=datetime.now(),
            scrape_time=date.today()
        )
        ```
    """

    artist_data: ArtistData
    venue_data: VenueData
    event_data: EventData
    performance_time: datetime
    scrape_time: date

    def validate(self) -> bool:
        """
        Validate the EventDTO instance.

        Returns:
            bool: True if valid, raises ValidationError if invalid

        Raises:
            ValidationError: If any required fields are missing or invalid
        """
        try:
            # Validate artist data
            if not self.artist_data.name:
                raise ValidationError(
                    message="Artist name is required",
                    error_type=ErrorType.VALIDATION_ERROR,
                    status_code=400,
                )

            # Validate venue data
            if not self.venue_data.name:
                raise ValidationError(
                    message="Venue name is required",
                    error_type=ErrorType.VALIDATION_ERROR,
                    status_code=400,
                )

            # Validate event data
            if not self.event_data.event_artist:
                raise ValidationError(
                    message="Event artist is required",
                    error_type=ErrorType.VALIDATION_ERROR,
                    status_code=400,
                )

            # Validate performance time
            if not self.performance_time:
                raise ValidationError(
                    message="Performance time is required",
                    error_type=ErrorType.VALIDATION_ERROR,
                    status_code=400,
                )

            # Validate scrape time
            if not self.scrape_time:
                raise ValidationError(
                    message="Scrape time is required",
                    error_type=ErrorType.VALIDATION_ERROR,
                    status_code=400,
                )

            return True

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during validation: {str(e)}")
            raise ValidationError(
                message=f"Unexpected validation error: {str(e)}",
                error_type=ErrorType.VALIDATION_ERROR,
                status_code=500,
            )

    def to_dict(self) -> dict:
        """
        Convert the EventDTO to a dictionary for JSON serialization.

        Returns:
            dict: A dictionary representation of the EventDTO

        Raises:
            ValidationError: If the DTO is invalid
        """
        try:
            # Validate before serialization
            self.validate()

            return {
                "artist_data": {
                    "name": self.artist_data.name,
                    "description": self.artist_data.description,
                    "wwoz_artist_href": self.artist_data.wwoz_artist_href,
                    "genres": self.artist_data.genres,
                    "related_artists": self.artist_data.related_artists,
                    "website": self.artist_data.website,
                },
                "venue_data": {
                    "name": self.venue_data.name,
                    "thoroughfare": self.venue_data.thoroughfare,
                    "phone_number": self.venue_data.phone_number,
                    "locality": self.venue_data.locality,
                    "state": self.venue_data.state,
                    "postal_code": self.venue_data.postal_code,
                    "full_address": self.venue_data.full_address,
                    "is_active": self.venue_data.is_active,
                    "website": self.venue_data.website,
                    "wwoz_venue_href": self.venue_data.wwoz_venue_href,
                    "event_artist": self.venue_data.event_artist,
                },
                "event_data": {
                    "event_date": self.event_data.event_date.isoformat(),
                    "wwoz_event_href": self.event_data.wwoz_event_href,
                    "event_artist": self.event_data.event_artist,
                    "wwoz_artist_href": self.event_data.wwoz_artist_href,
                    "description": self.event_data.description,
                    "related_artists": self.event_data.related_artists,
                    "genres": self.event_data.genres,
                },
                "performance_time": self.performance_time.isoformat(),
                "scrape_time": self.scrape_time.isoformat(),
            }
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error serializing EventDTO: {str(e)}")
            raise ValidationError(
                message=f"Error serializing event data: {str(e)}",
                error_type=ErrorType.VALIDATION_ERROR,
                status_code=500,
            )

    def get_artist_genres(self) -> List[str]:
        """
        Get a list of unique genres from both the artist and event.

        Returns:
            List[str]: List of unique genres
        """
        return list(set(self.artist_data.genres + self.event_data.genres))

    def get_venue_location(self) -> str:
        """
        Get a formatted venue location string.

        Returns:
            str: Formatted location string
        """
        parts = [
            self.venue_data.thoroughfare,
            self.venue_data.locality,
            self.venue_data.state,
            self.venue_data.postal_code,
        ]
        return ", ".join(filter(None, parts))

    def is_upcoming(self, reference_date: Optional[datetime] = None) -> bool:
        """
        Check if the event is upcoming relative to a reference date.

        Args:
            reference_date: Reference date to compare against (defaults to now)

        Returns:
            bool: True if the event is upcoming
        """
        if reference_date is None:
            reference_date = datetime.now()
        return self.performance_time > reference_date
