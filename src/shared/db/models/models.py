"""
Entity models for the database.
"""

from datetime import datetime
from urllib.parse import urljoin

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Interval,
    String,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from shared.db.models.relationships import (
    ARTIST_GENRE_TABLE,
    ARTIST_RELATION_TABLE,
    EVENT_GENRE_TABLE,
    VENUE_ARTIST_TABLE,
    VENUE_GENRE_TABLE,
)
from shared.utils.configs import base_configs

from . import Base


class Venue(Base):
    """
    Represents a venue entity in the database.

    Attributes:
        id (int): Primary key for the venue.
        name (str): Name of the venue. Cannot be null.
        phone_number (str): Contact phone number for the venue.
        thoroughfare (str): Street address of the venue.
        locality (str): City or locality of the venue.
        state (str): State where the venue is located.
        postal_code (str): Postal code of the venue.
        full_address (str): Full address of the venue.
        wwoz_venue_href (str): URL path for the venue on the WWOZ website.
        website (str): Official website of the venue.
        is_active (bool): Indicates if the venue is active. Defaults to True.
        latitude (float): Latitude coordinate of the venue.
        longitude (float): Longitude coordinate of the venue.
        capacity (int): Maximum capacity of the venue.
        is_indoors (bool): Indicates if the venue is an indoor venue. Defaults to True.
        last_updated (datetime): Timestamp of the last update to the venue record.
        last_geocoded (datetime): Timestamp of the last geocoding operation for the venue.
        description (str): Description of the venue.
        venue_info_embedding (Vector): Vector embedding for semantic search.

    Relationships:
        genres (list[Genre]): List of genres associated with the venue.
        events (list[Event]): List of events hosted at the venue.
        artists (list[Artist]): List of artists associated with the venue.

    Methods:
        full_url: Constructs the full URL for the venue using the base website URL.
        needs_geocoding: Determines if the venue requires geocoding based on its coordinates
                         and the last geocoding timestamp.
    """

    __tablename__ = "venues"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    phone_number = Column(String)
    thoroughfare = Column(String)
    locality = Column(String)
    state = Column(String)
    postal_code = Column(String)
    full_address = Column(String)
    wwoz_venue_href = Column(String)
    website = Column(String)
    is_active = Column(Boolean, default=True)
    latitude = Column(Float)
    longitude = Column(Float)
    capacity = Column(Integer)
    is_indoors = Column(Boolean, default=True)
    is_streaming = Column(Boolean, default=False)
    last_updated = Column(DateTime(timezone=True), server_default="now()")
    last_geocoded = Column(
        DateTime(timezone=True)
    )  # Track when we last geocoded this venue
    description = Column(Text)
    venue_info_embedding = Column(Vector(384))  # Vector embedding for semantic search

    genres = relationship("Genre", secondary=VENUE_GENRE_TABLE, back_populates="venues")
    events = relationship("Event", back_populates="venue")
    artists = relationship(
        "Artist", secondary=VENUE_ARTIST_TABLE, back_populates="venues"
    )

    @hybrid_property
    def full_url(self):
        """Construct the full URL."""
        return urljoin(base_configs["base_url"], self.wwoz_venue_href)

    def needs_geocoding(self) -> bool:
        """Check if venue needs geocoding."""
        if not self.latitude or not self.longitude:
            return True
        if not self.last_geocoded:
            return True
        # Re-geocode if it's been more than 30 days
        return (datetime.now(base_configs["timezone"]) - self.last_geocoded).days > 30


class Artist(Base):
    """
    Represents an artist in the database.

    Attributes:
        id (int): The primary key of the artist.
        name (str): The name of the artist. Cannot be null.
        wwoz_artist_href (str): A hyperlink reference to the artist's WWOZ page.
        description (str): A description of the artist.
        popularity_score (float): The popularity score of the artist.
        typical_set_length (Interval): The typical set length of the artist.
        website (str): The artist's official website.
        description_embedding (Vector): Vector embedding for semantic search.

    Relationships:
        events (list[Event]): A list of events associated with the artist.
        venues (list[Venue]): A list of venues where the artist has performed,
            through the "venue_artists" association table.
        genres (list[Genre]): A list of genres associated with the artist,
            through the "artist_genres" association table.
        related_artists (list[Artist]): A list of artists related to this artist,
            through the "artist_relations" association table.
        related_by_artists (list[Artist]): A list of artists that have this artist
            as a related artist, through the "artist_relations" association table.
    """

    __tablename__ = "artists"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    wwoz_artist_href = Column(String)
    description = Column(Text)
    popularity_score = Column(Float)
    typical_set_length = Column(Interval)
    website = Column(String(255))
    description_embedding = Column(Vector(384))  # Vector embedding for semantic search

    events = relationship("Event", back_populates="artist")
    venues = relationship(
        "Venue", secondary=VENUE_ARTIST_TABLE, back_populates="artists"
    )
    genres = relationship(
        "Genre", secondary=ARTIST_GENRE_TABLE, back_populates="artists"
    )
    related_artists = relationship(
        "Artist",
        secondary=ARTIST_RELATION_TABLE,
        primaryjoin="Artist.id==ArtistRelation.artist_id",
        secondaryjoin="Artist.id==ArtistRelation.related_artist_id",
        back_populates="related_by_artists",
    )
    related_by_artists = relationship(
        "Artist",
        secondary=ARTIST_RELATION_TABLE,
        primaryjoin="Artist.id==ArtistRelation.related_artist_id",
        secondaryjoin="Artist.id==ArtistRelation.artist_id",
        back_populates="related_artists",
    )


class Event(Base):
    """
    Represents an event in the database.

    Attributes:
        id (int): Primary key for the event.
        wwoz_event_href (str): URL reference for the event.
        description (str): Description of the event.
        artist_id (int): Foreign key referencing the associated artist.
        venue_id (int): Foreign key referencing the associated venue.
        artist_name (str): Name of the artist performing at the event.
        venue_name (str): Name of the venue hosting the event.
        performance_time (datetime): Start time of the performance (timezone-aware).
        end_time (datetime): End time of the performance (timezone-aware).
        scrape_time (date): Date when the event was scraped.
        last_updated (datetime): Timestamp of the last update (defaults to current time).
        is_recurring (bool): Indicates if the event is recurring.
        recurrence_pattern (str): Pattern for recurring events.
        is_indoors (bool): Indicates if the event is indoors (default is True).
        is_streaming (bool): Indicates if the event is streamed online (default is False).
        description_embedding (Vector): Vector embedding of the event description.
        event_text_embedding (Vector): Combined text embedding for semantic search.

    Relationships:
        artist (Artist): Relationship to the Artist model.
        venue (Venue): Relationship to the Venue model.
        genres (list[Genre]): List of genres associated with the event.

    Methods:
        full_url (str): Constructs the full URL for the event using the base website URL.
    """

    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    wwoz_event_href = Column(String)
    description = Column(Text)
    artist_id = Column(Integer, ForeignKey("artists.id"))
    venue_id = Column(Integer, ForeignKey("venues.id"))
    artist_name = Column(String)
    venue_name = Column(String)
    performance_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    scrape_time = Column(DateTime(timezone=True), nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default="now()")
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String)
    is_indoors = Column(Boolean, default=True)  # Default to indoors
    is_streaming = Column(Boolean, default=False)
    # Add vector embedding columns
    description_embedding = Column(Vector(384))  # Using all-MiniLM-L6-v2 model
    event_text_embedding = Column(Vector(384))  # Combined text for semantic search

    artist = relationship("Artist", back_populates="events")
    venue = relationship("Venue", back_populates="events")
    genres = relationship("Genre", secondary=EVENT_GENRE_TABLE, back_populates="events")

    @hybrid_property
    def full_url(self):
        """
        Construct the full URL by joining the base website URL with the event-specific href.

        Returns:
            str: The complete URL as a string.
        """
        return urljoin(Base.base_configs["base_url"], self.wwoz_event_href)


class Genre(Base):
    """
    Represents a music genre in the database.

    Attributes:
        id (int): The unique identifier for the genre.
        name (str): The name of the genre. Must be unique and cannot be null.
        description (str): Description of the genre.
        genre_embedding (Vector): Vector embedding for semantic search.
        venues (list[Venue]): A list of venues associated with this genre
          through the "venue_genres" association table.
        artists (list[Artist]): A list of artists associated with this
          genre through the "artist_genres" association table.
        events (list[Event]): A list of events associated with this genre
          through the "event_genres" association table.
    """

    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    genre_embedding = Column(Vector(384))  # Vector embedding for semantic search

    # Fixed relationships
    venues = relationship("Venue", secondary=VENUE_GENRE_TABLE, back_populates="genres")
    artists = relationship(
        "Artist", secondary=ARTIST_GENRE_TABLE, back_populates="genres"
    )
    events = relationship("Event", secondary=EVENT_GENRE_TABLE, back_populates="genres")
