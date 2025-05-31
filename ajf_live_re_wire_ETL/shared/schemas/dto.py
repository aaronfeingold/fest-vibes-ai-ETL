"""
Data Transfer Objects (DTOs) for the application.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List


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
    Data Transfer Object (DTO) representing an event.

    Attributes:
        artist_data (ArtistData): Information about the artist associated with the event.
        venue_data (VenueData): Information about the venue where the event is taking place.
        event_data (EventData): General information about the event.
        performance_time (datetime): The date and time when the event is scheduled to occur.
        scrape_time (date): The date when the event data was scraped or retrieved.
    """

    artist_data: ArtistData
    venue_data: VenueData
    event_data: EventData
    performance_time: datetime
    scrape_time: date
