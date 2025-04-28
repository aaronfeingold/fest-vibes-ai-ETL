"""
Models for the database.
"""

from sqlalchemy.ext.declarative import declarative_base

# Create the declarative base that all models will inherit from
Base = declarative_base()

from .models import Artist, Event, Genre, Venue

# Import all models after Base is defined
# this should be ignored by flake8
# flake8: noqa: E402
from .relationships import (
    ArtistGenre,
    ArtistRelation,
    EventGenre,
    VenueArtist,
    VenueGenre,
)

# Re-export everything for convenience
__all__ = [
    "Base",
    "ArtistRelation",
    "VenueArtist",
    "VenueGenre",
    "ArtistGenre",
    "EventGenre",
    "Venue",
    "Artist",
    "Event",
    "Genre",
]
