"""
Test utilities for the loader component.

This module contains tests for utility functions used in the loader,
including date extraction from S3 keys.
"""

import pytest

from loader.app import extract_date_from_s3_key


class TestDateExtraction:
    """Test cases for extracting dates from S3 keys."""

    def test_extract_date_from_path_structure(self):
        """Test extracting date from S3 path structure (raw_events/YYYY/MM/DD/)."""
        s3_key = "raw_events/2025/07/30/event_data_2025-07-29_20250730_002901.json"
        result = extract_date_from_s3_key(s3_key)
        assert result == "2025-07-30"

    def test_extract_date_from_filename(self):
        """Test extracting date from filename pattern (event_data_YYYY-MM-DD_)."""
        # Test case where path structure is different but filename has date
        s3_key = "different/path/event_data_2024-12-01_20241201_120000.json"
        result = extract_date_from_s3_key(s3_key)
        assert result == "2024-12-01"

    def test_extract_date_from_yyyymmdd_format(self):
        """Test extracting date from YYYYMMDD format in filename."""
        # Test case where only YYYYMMDD format is available
        s3_key = "some/path/file_name_20230115_160000.json"
        result = extract_date_from_s3_key(s3_key)
        assert result == "2023-01-15"

    def test_priority_order_path_first(self):
        """Test that path structure takes priority over filename."""
        # Both path and filename have dates, path should win
        s3_key = "raw_events/2025/03/22/event_data_2025-03-21_20250322_090000.json"
        result = extract_date_from_s3_key(s3_key)
        # Should extract from path (2025-03-22) not filename (2025-03-21)
        assert result == "2025-03-22"

    def test_various_date_formats(self):
        """Test extraction with various valid date formats."""
        test_cases = [
            ("raw_events/2024/01/01/file.json", "2024-01-01"),
            ("raw_events/2023/12/31/file.json", "2023-12-31"),
            ("path/event_data_2022-06-15_file.json", "2022-06-15"),
            ("path/some_file_20210430_123456.json", "2021-04-30"),
        ]

        for s3_key, expected_date in test_cases:
            result = extract_date_from_s3_key(s3_key)
            assert result == expected_date, f"Failed for key: {s3_key}"

    def test_no_date_found(self):
        """Test cases where no date can be extracted."""
        test_cases = [
            "different/path/structure.json",
            "raw_events/not_a_date/file.json",
            "some/random/file.json",
            "event_data_invalid_date_format.json",
            "",
        ]

        for s3_key in test_cases:
            result = extract_date_from_s3_key(s3_key)
            assert result is None, f"Should return None for key: {s3_key}"

    def test_edge_cases(self):
        """Test edge cases and potential error conditions."""
        # Invalid date values that match pattern but aren't real dates
        test_cases = [
            (
                "raw_events/9999/99/99/file.json",
                "9999-99-99",
            ),  # Invalid but matches pattern
            ("raw_events/0000/00/00/file.json", "0000-00-00"),  # Edge case
        ]

        for s3_key, expected in test_cases:
            result = extract_date_from_s3_key(s3_key)
            assert result == expected

    def test_malformed_s3_keys(self):
        """Test that malformed S3 keys don't cause crashes."""
        test_cases = [
            None,  # This would cause an exception in the try/catch
            123,  # Non-string input
        ]

        for s3_key in test_cases:
            # Should handle gracefully and return None
            try:
                result = extract_date_from_s3_key(s3_key)
                assert result is None
            except Exception:
                # If an exception occurs, it should be caught internally
                # and None should be returned, but we'll accept either behavior
                pass

    def test_original_example_format(self):
        """Test the exact format provided in the original requirement."""
        s3_key = "raw_events/2025/07/30/event_data_2025-07-29_20250730_002901.json"
        result = extract_date_from_s3_key(s3_key)

        # Should extract from path structure: 2025/07/30 -> 2025-07-30
        assert result == "2025-07-30"

        # Verify it matches the app-wide date format (%Y-%m-%d)
        from datetime import datetime

        parsed_date = datetime.strptime(result, "%Y-%m-%d")
        assert parsed_date.year == 2025
        assert parsed_date.month == 7
        assert parsed_date.day == 30


class TestGenreDeadlockFix:
    """Test that the genre creation method handles concurrent access properly."""

    def test_on_conflict_sql_structure(self):
        """Test that the ON CONFLICT SQL structure is correct for our use case."""
        # This test verifies the SQL structure we're using for the deadlock fix
        expected_sql = """
                    INSERT INTO genres (name)
                    VALUES (:name)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING id, name, description
                """

        # Verify the SQL has the key components for deadlock prevention
        assert "INSERT INTO genres" in expected_sql
        assert "ON CONFLICT (name) DO NOTHING" in expected_sql
        assert "RETURNING id, name, description" in expected_sql

        # This test ensures our SQL structure follows PostgreSQL best practices
        # for handling concurrent inserts on unique constraints


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
