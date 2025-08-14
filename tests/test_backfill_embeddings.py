"""
Test the embedding backfill functionality
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent / "src")
sys.path.insert(0, project_root)

from shared.db.migrations.backfill_existing_embeddings import (  # noqa: E402
    EmbeddingBackfillService,
)
from shared.db.models import Artist, Genre, Venue  # noqa: E402


class TestEmbeddingBackfill:
    """Test the embedding backfill functionality."""

    @pytest.fixture
    def mock_backfill_service(self):
        """Create a mock backfill service."""
        service = EmbeddingBackfillService()

        # Mock the database service
        service.db_service = Mock()
        service.db_service.generate_embeddings_for_artist = Mock()
        service.db_service.generate_embeddings_for_venue = Mock()
        service.db_service.generate_embeddings_for_genre = Mock()
        service.db_service.close = Mock()

        return service

    def test_backfill_service_initialization(self):
        """Test that the backfill service initializes correctly."""
        service = EmbeddingBackfillService()

        # Check initial state
        assert service.db_service is None
        assert service.stats["artists_processed"] == 0
        assert service.stats["venues_processed"] == 0
        assert service.stats["genres_processed"] == 0
        assert service.stats["errors"] == 0

    def test_stats_tracking_structure(self, mock_backfill_service):
        """Test that statistics tracking has the correct structure."""
        stats = mock_backfill_service.stats

        required_keys = [
            "artists_processed",
            "venues_processed",
            "genres_processed",
            "artists_updated",
            "venues_updated",
            "genres_updated",
            "errors",
        ]

        for key in required_keys:
            assert key in stats
            assert isinstance(stats[key], int)

    @pytest.mark.asyncio
    async def test_backfill_genre_embeddings(self, mock_backfill_service):
        """Test genre embedding backfill functionality."""
        # Create mock genres
        genres = [
            Genre(id=1, name="Jazz", description="Jazz music"),
            Genre(id=2, name="Blues", description="Blues music"),
            Genre(id=3, name="Funk", description=None),  # Test fallback
        ]

        # Mock session with async commit
        mock_session = Mock()
        mock_session.commit = AsyncMock()

        # Mock the embedding generation to set embeddings
        async def mock_generate_genre_embedding(genre):
            genre.genre_embedding = [0.1, 0.2, 0.3] * 128  # 384 dimensions

        mock_backfill_service.db_service.generate_embeddings_for_genre.side_effect = (
            mock_generate_genre_embedding
        )

        # Run backfill
        await mock_backfill_service.backfill_genre_embeddings(mock_session, genres)

        # Check statistics
        assert mock_backfill_service.stats["genres_processed"] == 3
        assert mock_backfill_service.stats["genres_updated"] == 3

        # Verify embedding generation was called for each genre
        assert (
            mock_backfill_service.db_service.generate_embeddings_for_genre.call_count
            == 3
        )

        # Verify session commits (should commit after batch and at end)
        assert mock_session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_backfill_artist_embeddings(self, mock_backfill_service):
        """Test artist embedding backfill functionality."""
        # Create mock artists
        artists = [
            Artist(id=1, name="Test Artist 1", description="Jazz musician"),
            Artist(id=2, name="Test Artist 2", description="Blues singer"),
        ]

        # Mock session with async commit
        mock_session = Mock()
        mock_session.commit = AsyncMock()

        # Mock the embedding generation
        async def mock_generate_artist_embedding(artist):
            artist.description_embedding = [0.1, 0.2, 0.3] * 128

        mock_backfill_service.db_service.generate_embeddings_for_artist.side_effect = (
            mock_generate_artist_embedding
        )

        # Run backfill
        await mock_backfill_service.backfill_artist_embeddings(mock_session, artists)

        # Check statistics
        assert mock_backfill_service.stats["artists_processed"] == 2
        assert mock_backfill_service.stats["artists_updated"] == 2

        # Verify methods called
        assert (
            mock_backfill_service.db_service.generate_embeddings_for_artist.call_count
            == 2
        )

    @pytest.mark.asyncio
    async def test_backfill_venue_embeddings(self, mock_backfill_service):
        """Test venue embedding backfill functionality."""
        # Create mock venues
        venues = [
            Venue(id=1, name="Test Venue 1", full_address="123 Test St"),
            Venue(id=2, name="Test Venue 2", full_address="456 Test Ave"),
        ]

        # Mock session with async commit
        mock_session = Mock()
        mock_session.commit = AsyncMock()

        # Mock the embedding generation
        async def mock_generate_venue_embedding(venue):
            venue.venue_info_embedding = [0.1, 0.2, 0.3] * 128

        mock_backfill_service.db_service.generate_embeddings_for_venue.side_effect = (
            mock_generate_venue_embedding
        )

        # Run backfill
        await mock_backfill_service.backfill_venue_embeddings(mock_session, venues)

        # Check statistics
        assert mock_backfill_service.stats["venues_processed"] == 2
        assert mock_backfill_service.stats["venues_updated"] == 2

        # Verify methods called
        assert (
            mock_backfill_service.db_service.generate_embeddings_for_venue.call_count
            == 2
        )

    @pytest.mark.asyncio
    async def test_error_handling_in_backfill(self, mock_backfill_service):
        """Test that errors during backfill are handled gracefully."""
        # Create mock genres
        genres = [
            Genre(id=1, name="Jazz", description="Jazz music"),
            Genre(id=2, name="Broken Genre", description="This will fail"),
        ]

        # Mock session with async commit
        mock_session = Mock()
        mock_session.commit = AsyncMock()

        # Mock embedding generation to fail for second genre
        async def mock_generate_with_error(genre):
            if genre.name == "Broken Genre":
                raise Exception("Embedding generation failed")
            genre.genre_embedding = [0.1, 0.2, 0.3] * 128

        mock_backfill_service.db_service.generate_embeddings_for_genre.side_effect = (
            mock_generate_with_error
        )

        # Run backfill (should not raise exception)
        await mock_backfill_service.backfill_genre_embeddings(mock_session, genres)

        # Check that processing continued despite error
        assert mock_backfill_service.stats["genres_processed"] == 2
        assert (
            mock_backfill_service.stats["genres_updated"] == 1
        )  # Only first succeeded
        assert mock_backfill_service.stats["errors"] == 1

    def test_backfill_script_has_proper_structure(self):
        """Test that the backfill script has the required structure."""
        # Import the script module using importlib
        import importlib.util

        script_path = (
            Path(__file__).parent.parent
            / "src"
            / "shared"
            / "db"
            / "migrations"
            / "backfill_existing_embeddings.py"
        )
        spec = importlib.util.spec_from_file_location("backfill_module", script_path)
        backfill_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backfill_module)

        # Check that main function exists
        assert hasattr(backfill_module, "main")
        assert callable(backfill_module.main)

        # Check that service class exists
        assert hasattr(backfill_module, "EmbeddingBackfillService")

        # Check that service has required methods
        service_methods = [
            "initialize",
            "get_entities_without_embeddings",
            "backfill_genre_embeddings",
            "backfill_artist_embeddings",
            "backfill_venue_embeddings",
            "run_backfill",
        ]

        for method_name in service_methods:
            assert hasattr(backfill_module.EmbeddingBackfillService, method_name)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
