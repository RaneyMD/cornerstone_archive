"""Unit tests for stage1 parse_ia_metadata module."""

import pytest
from datetime import datetime

from scripts.stage1.parse_ia_metadata import (
    parse_ia_metadata,
    validate_ia_metadata,
    map_to_instance_key,
    MetadataParseError,
    MetadataValidationError,
)


class TestParseIAMetadata:
    """Tests for parse_ia_metadata function."""

    @pytest.fixture
    def sample_ia_response(self):
        """Sample IA API response."""
        return {
            "id": "sim_american-architect_1876_05",
            "metadata": {
                "title": "American Architect, Vol 1, No 5 (May 1876)",
                "description": "Architectural journal, 48 pages",
                "creator": "The American Architect",
                "date": "1876-05-05",
                "year": "1876",
                "pages": 48,
                "language": "English",
                "publisher": "Wm. T. Comstock",
                "subject": "Architecture",
            },
            "files": [
                {"name": "page_001.jp2", "size": 5000000},
                {"name": "page_002.jp2", "size": 5100000},
                {"name": "page_003.jp2", "size": 5200000},
                {"name": "item_1876_05_hocr.xml", "size": 50000},
            ],
        }

    def test_parse_success(self, sample_ia_response):
        """Test successful metadata parsing."""
        result = parse_ia_metadata(sample_ia_response)

        assert result["ia_id"] == "sim_american-architect_1876_05"
        assert result["title"] == "American Architect, Vol 1, No 5 (May 1876)"
        assert result["extent_pages"] == 48
        assert result["publication_date"] == "1876-05-05"
        assert result["publication_year"] == 1876
        assert result["jp2_count"] == 3
        assert result["ocr_available"] is True

    def test_parse_minimal_metadata(self):
        """Test parsing minimal required metadata."""
        ia_response = {
            "id": "test_item",
            "metadata": {
                "title": "Test Item",
            },
            "files": [
                {"name": "page_001.jp2"},
                {"name": "page_002.jp2"},
            ],
        }

        result = parse_ia_metadata(ia_response)

        assert result["ia_id"] == "test_item"
        assert result["extent_pages"] == 2  # From file count
        assert result["jp2_count"] == 2

    def test_parse_missing_required_fields(self):
        """Test parsing with missing required fields raises error."""
        ia_response = {
            "id": "test_item",
            "metadata": {},  # Missing title
            "files": [{"name": "page.jp2"}],
        }

        # Should raise MetadataValidationError (wrapper in MetadataParseError)
        with pytest.raises((MetadataParseError, MetadataValidationError)):
            parse_ia_metadata(ia_response)


class TestValidateIAMetadata:
    """Tests for validate_ia_metadata function."""

    def test_validate_success(self):
        """Test successful validation."""
        metadata = {
            "ia_id": "test_id",
            "title": "Test Title",
            "extent_pages": 42,
            "publication_year": 1876,
            "jp2_count": 42,
        }

        validate_ia_metadata(metadata)  # Should not raise

    def test_validate_missing_ia_id(self):
        """Test validation fails without IA ID."""
        metadata = {
            "title": "Test",
            "extent_pages": 42,
            "jp2_count": 42,
        }

        with pytest.raises(MetadataValidationError, match="IA ID"):
            validate_ia_metadata(metadata)

    def test_validate_missing_title(self):
        """Test validation fails without title."""
        metadata = {
            "ia_id": "test",
            "extent_pages": 42,
            "jp2_count": 42,
        }

        with pytest.raises(MetadataValidationError, match="title"):
            validate_ia_metadata(metadata)

    def test_validate_invalid_extent_pages(self):
        """Test validation fails with invalid page count."""
        metadata = {
            "ia_id": "test",
            "title": "Test",
            "extent_pages": 0,
            "jp2_count": 42,
        }

        with pytest.raises(MetadataValidationError, match="extent_pages"):
            validate_ia_metadata(metadata)

    def test_validate_invalid_publication_year(self):
        """Test validation fails with invalid year."""
        metadata = {
            "ia_id": "test",
            "title": "Test",
            "extent_pages": 42,
            "publication_year": 1776,  # Too early
            "jp2_count": 42,
        }

        with pytest.raises(MetadataValidationError, match="publication year"):
            validate_ia_metadata(metadata)

    def test_validate_missing_jp2_files(self):
        """Test validation fails without JP2 files."""
        metadata = {
            "ia_id": "test",
            "title": "Test",
            "extent_pages": 42,
            "jp2_count": 0,
        }

        with pytest.raises(MetadataValidationError, match="JP2"):
            validate_ia_metadata(metadata)

    def test_validate_future_year_acceptable(self):
        """Test that future year is accepted (for scheduled publications)."""
        current_year = datetime.now().year
        metadata = {
            "ia_id": "test",
            "title": "Test",
            "extent_pages": 42,
            "publication_year": current_year + 1,
            "jp2_count": 42,
        }

        validate_ia_metadata(metadata)  # Should not raise


class TestMapToInstanceKey:
    """Tests for map_to_instance_key function."""

    def test_map_to_instance_key_basic(self):
        """Test basic instance key mapping."""
        metadata = {
            "ia_id": "sim_american-architect_1876_05",
            "publication_date": "1876-05-05",
        }

        key = map_to_instance_key(metadata, family_code="AA")

        # Should have expected format parts
        assert key.startswith("AA_is_")
        assert "1876" in key
        assert "05" in key  # Month or issue

    def test_map_to_instance_key_missing_date(self):
        """Test mapping with missing publication date."""
        metadata = {
            "ia_id": "test_id",
            "publication_date": None,
        }

        key = map_to_instance_key(metadata, family_code="TEST")

        # Should use default date
        assert key.startswith("TEST_is_1900")

    def test_map_to_instance_key_default_family(self):
        """Test mapping with default family code."""
        metadata = {
            "ia_id": "test",
            "publication_date": "2020-01-15",
        }

        key = map_to_instance_key(metadata)

        assert key.startswith("test_is_")

    def test_map_to_instance_key_reproducible(self):
        """Test that same metadata produces same key."""
        metadata = {
            "ia_id": "sim_test_1900_01",
            "publication_date": "1900-01-01",
        }

        key1 = map_to_instance_key(metadata, family_code="T")
        key2 = map_to_instance_key(metadata, family_code="T")

        assert key1 == key2


class TestDateNormalization:
    """Tests for date parsing and normalization."""

    def test_parse_date_iso_format(self):
        """Test parsing ISO date format."""
        from scripts.stage1.parse_ia_metadata import _normalize_date

        result = _normalize_date("2020-05-15")
        assert result == "2020-05-15"

    def test_parse_date_us_format(self):
        """Test parsing US date format."""
        from scripts.stage1.parse_ia_metadata import _normalize_date

        result = _normalize_date("05/15/2020")
        assert result == "2020-05-15"

    def test_parse_date_written_format(self):
        """Test parsing written date format."""
        from scripts.stage1.parse_ia_metadata import _normalize_date

        result = _normalize_date("May 15, 2020")
        assert result == "2020-05-15"

    def test_parse_date_year_only(self):
        """Test parsing year only."""
        from scripts.stage1.parse_ia_metadata import _normalize_date

        result = _normalize_date("1876")
        assert result == "1876-01-01"

    def test_parse_date_invalid(self):
        """Test parsing invalid date."""
        from scripts.stage1.parse_ia_metadata import _normalize_date

        result = _normalize_date("invalid date")
        assert result is None

    def test_parse_date_empty(self):
        """Test parsing empty date."""
        from scripts.stage1.parse_ia_metadata import _normalize_date

        result = _normalize_date("")
        assert result is None
