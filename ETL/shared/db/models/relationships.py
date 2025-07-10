"""
Base models for the database and join tables.
"""

from sqlalchemy import Column, ForeignKey, Index, Integer

from . import Base

# Table names for relationships
VENUE_ARTIST_TABLE = "venue_artists"
VENUE_GENRE_TABLE = "venue_genres"
ARTIST_GENRE_TABLE = "artist_genres"
EVENT_GENRE_TABLE = "event_genres"
ARTIST_RELATION_TABLE = "artist_relations"


class ArtistRelation(Base):
    """
    Represents a relationship between two artists in the database.

    This model defines a many-to-many relationship between artists, where each
    artist can have multiple related artists. The relationship is stored in the
    `artist_relations` table.

    Attributes:
        artist_id (int): The ID of the artist. This is a foreign key referencing
            the `id` column in the `artists` table. It is part of the composite
            primary key.
        related_artist_id (int): The ID of the related artist. This is a foreign
            key referencing the `id` column in the `artists` table. It is part of
            the composite primary key.

    Table Arguments:
        __table_args__:
            - Index("ix_artist_relation_artist_id", artist_id): Index for the
              `artist_id` column to optimize queries.
            - Index("ix_artist_relation_related_artist_id", related_artist_id):
              Index for the `related_artist_id` column to optimize queries.
    """

    __tablename__ = ARTIST_RELATION_TABLE

    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    related_artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_artist_relation_artist_id", artist_id),
        Index("ix_artist_relation_related_artist_id", related_artist_id),
    )


class VenueArtist(Base):
    """
    Represents the association between venues and artists in a many-to-many relationship.

    Attributes:
        venue_id (int): The ID of the venue. Foreign key referencing the 'venues' table.
        artist_id (int): The ID of the artist. Foreign key referencing the 'artists' table.

    Table Arguments:
        __tablename__ (str): The name of the table in the database ('venue_artists').
        __table_args__ (tuple): Additional table arguments, including indexes:
            - Index on 'venue_id' (ix_venue_artist_venue_id).
            - Index on 'artist_id' (ix_venue_artist_artist_id).
    """

    __tablename__ = VENUE_ARTIST_TABLE

    venue_id = Column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_venue_artist_venue_id", venue_id),
        Index("ix_venue_artist_artist_id", artist_id),
    )


class VenueGenre(Base):
    """
    Represents the association table for a many-to-many relationship between venues and genres.

    Attributes:
        venue_id (int): The ID of the venue, serving as a foreign key to the "venues" table.
        genre_id (int): The ID of the genre, serving as a foreign key to the "genres" table.

    Table Arguments:
        __tablename__ (str): The name of the table in the database ("venue_genres").
        __table_args__ (tuple): Additional table arguments, including:
            - Index on `venue_id` for optimized queries.
            - Index on `genre_id` for optimized queries.
    """

    __tablename__ = VENUE_GENRE_TABLE

    venue_id = Column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = Column(
        Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_venue_genre_venue_id", venue_id),
        Index("ix_venue_genre_genre_id", genre_id),
    )


class ArtistGenre(Base):
    """
    Represents the association table for a many-to-many relationship between artists and genres.

    Attributes:
        artist_id (int): Foreign key referencing the ID of an artist. Acts as a primary key.
        genre_id (int): Foreign key referencing the ID of a genre. Acts as a primary key.

    Table Arguments:
        __tablename__ (str): The name of the table in the database ("artist_genres").
        __table_args__ (tuple): Contains additional table arguments, including:
            - Index on artist_id ("ix_artist_genre_artist_id").
            - Index on genre_id ("ix_artist_genre_genre_id").
    """

    __tablename__ = ARTIST_GENRE_TABLE

    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = Column(
        Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_artist_genre_artist_id", artist_id),
        Index("ix_artist_genre_genre_id", genre_id),
    )


class EventGenre(Base):
    """
    Represents the association table for a many-to-many relationship between events and genres.

    This class defines the `event_genres` table, which links events to their associated genres.
    Each row in the table corresponds to a relationship between an event and a genre.

    Attributes:
        event_id (int): The ID of the event, serving as a foreign key to the `events` table.
        genre_id (int): The ID of the genre, serving as a foreign key to the `genres` table.

    Table Arguments:
        __table_args__:
            - Index("ix_event_genre_event_id", event_id):
              Index for optimizing queries by `event_id`.
            - Index("ix_event_genre_genre_id", genre_id):
              Index for optimizing queries by `genre_id`.
    """

    __tablename__ = EVENT_GENRE_TABLE

    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = Column(
        Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        Index("ix_event_genre_event_id", event_id),
        Index("ix_event_genre_genre_id", genre_id),
    )
