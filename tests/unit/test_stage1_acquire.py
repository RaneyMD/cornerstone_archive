"""Unit tests for stage1 acquire_source handler."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import requests

from scripts.stage1.acquire_source import (
    acquire_source,
    fetch_ia_metadata,
    download_ia_container,
    validate_downloads,
    register_container_in_db,
    IAError,
    DownloadError,
    DownloadValidationError,
)


class TestFetchIAMetadata:
    """Tests for fetch_ia_metadata function."""

    def test_fetch_success(self):
        """Test successful metadata fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "metadata": {
                "title": "Test Item",
                "pages": 42,
                "date": "2020-01-01",
            },
            "files": [
                {"name": "page_001.jp2", "size": 5000000, "md5": "abc123"},
                {"name": "page_002.jp2", "size": 5000000, "md5": "def456"},
            ],
        }

        with patch("scripts.stage1.acquire_source.requests.get", return_value=mock_response):
            result = fetch_ia_metadata("test_item")

            assert result["ia_id"] == "test_item"
            assert result["title"] == "Test Item"
            assert result["extent_pages"] == 42
            assert len(result["files"]) == 2

    def test_fetch_network_timeout(self):
        """Test handling network timeout."""
        with patch(
            "scripts.stage1.acquire_source.requests.get",
            side_effect=requests.exceptions.Timeout(),
        ):
            with pytest.raises(IAError, match="timeout"):
                fetch_ia_metadata("test_item")

    def test_fetch_http_error(self):
        """Test handling HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")

        with patch("scripts.stage1.acquire_source.requests.get", return_value=mock_response):
            with pytest.raises(IAError):
                fetch_ia_metadata("test_item")

    def test_fetch_invalid_json(self):
        """Test handling invalid JSON response."""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

        with patch("scripts.stage1.acquire_source.requests.get", return_value=mock_response):
            with pytest.raises(IAError, match="parse"):
                fetch_ia_metadata("test_item")

    def test_fetch_with_retry(self):
        """Test retry logic on timeout."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "metadata": {"title": "Test", "pages": 10},
            "files": [{"name": "page.jp2"}],
        }

        with patch("scripts.stage1.acquire_source.requests.get") as mock_get:
            mock_get.side_effect = [
                requests.exceptions.Timeout(),
                mock_response,
            ]

            with patch("scripts.stage1.acquire_source.time.sleep"):
                result = fetch_ia_metadata("test_item", max_retries=2)

                assert result["ia_id"] == "test_item"
                assert mock_get.call_count == 2


class TestDownloadIAContainer:
    """Tests for download_ia_container function."""

    @pytest.fixture
    def temp_nas(self, tmp_path):
        """Create temporary NAS structure."""
        nas = MagicMock()
        raw_path = tmp_path / "01_RAW" / "containers" / "1"
        raw_path.mkdir(parents=True)
        nas.get_raw_path.return_value = raw_path
        return nas

    @pytest.fixture
    def mock_ia_metadata(self):
        """Mock IA metadata."""
        return {
            "files": [
                {"name": "page_001.jp2", "size": 1000000},
                {"name": "page_002.jp2", "size": 1000000},
            ]
        }

    def test_download_success(self, temp_nas, mock_ia_metadata):
        """Test successful download."""
        mock_response = MagicMock()
        # Create mock data of correct size (1000000 bytes)
        mock_response.iter_content.return_value = [b"x" * 1000000]

        with patch("scripts.stage1.acquire_source.requests.get", return_value=mock_response):
            with patch("scripts.stage1.acquire_source.fetch_ia_metadata", return_value=mock_ia_metadata):
                with patch("scripts.stage1.acquire_source.time.sleep"):
                    result = download_ia_container("test_item", "1", temp_nas)

                    assert result["pages_downloaded"] == 2
                    assert result["jp2_files"] == 2
                    assert result["size_bytes"] > 0

    def test_download_size_mismatch(self, temp_nas, mock_ia_metadata):
        """Test handling download size mismatch."""
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"x"]  # Only 1 byte

        with patch("scripts.stage1.acquire_source.requests.get", return_value=mock_response):
            with patch("scripts.stage1.acquire_source.fetch_ia_metadata", return_value=mock_ia_metadata):
                with patch("scripts.stage1.acquire_source.time.sleep"):
                    # Should fail on size mismatch and retry
                    with pytest.raises(DownloadError):
                        download_ia_container("test_item", "1", temp_nas, max_retries=1)

    def test_download_network_error(self, temp_nas, mock_ia_metadata):
        """Test handling network errors during download."""
        with patch(
            "scripts.stage1.acquire_source.requests.get",
            side_effect=requests.exceptions.ConnectionError(),
        ):
            with patch("scripts.stage1.acquire_source.fetch_ia_metadata", return_value=mock_ia_metadata):
                with patch("scripts.stage1.acquire_source.time.sleep"):
                    with pytest.raises(DownloadError):
                        download_ia_container("test_item", "1", temp_nas, max_retries=1)


class TestValidateDownloads:
    """Tests for validate_downloads function."""

    def test_validate_success(self, tmp_path):
        """Test successful validation."""
        # Create JP2 files
        (tmp_path / "page_001.jp2").touch()
        (tmp_path / "page_002.jp2").touch()

        metadata = {"files": [{"name": "page_001.jp2"}, {"name": "page_002.jp2"}]}

        validate_downloads("1", tmp_path, metadata)  # Should not raise

    def test_validate_file_count_mismatch(self, tmp_path):
        """Test validation fails with mismatched file count."""
        (tmp_path / "page_001.jp2").touch()

        metadata = {"files": [{"name": "page_001.jp2"}, {"name": "page_002.jp2"}]}

        with pytest.raises(DownloadValidationError, match="count"):
            validate_downloads("1", tmp_path, metadata)

    def test_validate_empty_directory(self, tmp_path):
        """Test validation fails with empty directory."""
        metadata = {"files": [{"name": "page_001.jp2"}]}

        with pytest.raises(DownloadValidationError):
            validate_downloads("1", tmp_path, metadata)


class TestRegisterContainerInDB:
    """Tests for register_container_in_db function."""

    def test_register_success(self):
        """Test successful database registration."""
        mock_db = MagicMock()
        ia_metadata = {"extent_pages": 42}
        download_stats = {"pages_downloaded": 42}

        register_container_in_db("1", "test_item", mock_db, ia_metadata, download_stats)

        # Verify database was called
        assert mock_db.execute.call_count >= 1
        assert mock_db.execute_many.call_count >= 1

    def test_register_database_error(self):
        """Test handling database errors."""
        from scripts.common.spec_db import DatabaseError

        mock_db = MagicMock()
        mock_db.execute.side_effect = DatabaseError("Connection failed")

        ia_metadata = {"extent_pages": 42}
        download_stats = {"pages_downloaded": 42}

        with pytest.raises(DatabaseError):
            register_container_in_db("1", "test_item", mock_db, ia_metadata, download_stats)


class TestAcquireSourceHandler:
    """Tests for main acquire_source handler."""

    def test_acquire_source_success(self):
        """Test successful acquisition."""
        mock_nas = MagicMock()
        mock_nas.get_raw_path.return_value = Path("/tmp/01_RAW/containers/1")

        mock_db = MagicMock()

        task = {
            "task_id": "test_001",
            "container_id": 1,
            "params": {"ia_identifier": "test_item"},
        }

        with patch("scripts.stage1.acquire_source.fetch_ia_metadata") as mock_fetch:
            with patch("scripts.stage1.acquire_source.download_ia_container") as mock_download:
                with patch("scripts.stage1.acquire_source.validate_downloads"):
                    with patch("scripts.stage1.acquire_source.register_container_in_db"):
                        mock_fetch.return_value = {"extent_pages": 42, "files": []}
                        mock_download.return_value = {
                            "pages_downloaded": 42,
                            "jp2_files": 42,
                            "ocr_files": 0,
                            "size_bytes": 1000000,
                        }

                        result = acquire_source(task, mock_nas, mock_db)

                        assert result["status"] == "success"
                        assert result["container_id"] == 1
                        assert result["ia_identifier"] == "test_item"
                        assert result["pages_downloaded"] == 42

    def test_acquire_source_missing_params(self):
        """Test error handling with missing parameters."""
        mock_nas = MagicMock()
        mock_db = MagicMock()

        task = {"task_id": "test_001", "container_id": 1, "params": {}}

        with pytest.raises(ValueError, match="ia_identifier"):
            acquire_source(task, mock_nas, mock_db)

    def test_acquire_source_network_error(self):
        """Test error handling for network errors."""
        mock_nas = MagicMock()
        mock_db = MagicMock()

        task = {
            "task_id": "test_001",
            "container_id": 1,
            "params": {"ia_identifier": "test_item"},
        }

        with patch("scripts.stage1.acquire_source.fetch_ia_metadata") as mock_fetch:
            mock_fetch.side_effect = IAError("Network unreachable")

            with pytest.raises(IAError):
                acquire_source(task, mock_nas, mock_db)
