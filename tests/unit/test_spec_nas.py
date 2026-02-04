"""Unit tests for spec_nas module."""

import os
import pytest
import tempfile
from pathlib import Path

from scripts.common.spec_nas import NasManager, NasError


class TestNasManager:
    """Tests for NasManager class."""

    @pytest.fixture
    def temp_nas_root(self):
        """Create a temporary NAS root directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nas_root = Path(tmpdir)
            # Create standard directories
            (nas_root / "00_STATE").mkdir(exist_ok=True)
            (nas_root / "01_RAW" / "containers").mkdir(parents=True, exist_ok=True)
            (nas_root / "02_WORK" / "containers").mkdir(parents=True, exist_ok=True)
            (nas_root / "03_REFERENCE").mkdir(exist_ok=True)
            (nas_root / "04_PUBLISH").mkdir(exist_ok=True)
            (nas_root / "05_LOGS").mkdir(exist_ok=True)
            yield nas_root

    @pytest.fixture
    def config_with_nas(self, temp_nas_root):
        """Create a config with temporary NAS root."""
        return {
            "nas": {"root": str(temp_nas_root)},
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
        }

    def test_init_invalid_config_type(self):
        """Test initialization with invalid config type."""
        with pytest.raises(NasError, match="Config must be a dictionary"):
            NasManager("not a dict")

    def test_init_missing_nas_root(self):
        """Test initialization with missing nas.root."""
        with pytest.raises(NasError, match="nas.root"):
            NasManager({"nas": {}})

    def test_init_nas_root_not_exists(self):
        """Test initialization when NAS root doesn't exist."""
        with pytest.raises(NasError, match="does not exist"):
            NasManager({"nas": {"root": "/nonexistent/path/that/does/not/exist"}})

    def test_init_nas_root_not_readable(self):
        """Test initialization when NAS root is not readable."""
        # Skip on Windows since permission model is different
        import sys
        if sys.platform == "win32":
            pytest.skip("Permission model differs on Windows")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # Make directory unreadable
            os.chmod(tmpdir_path, 0o000)
            try:
                with pytest.raises(NasError, match="not readable"):
                    NasManager({"nas": {"root": str(tmpdir_path)}})
            finally:
                # Restore permissions for cleanup
                os.chmod(tmpdir_path, 0o755)

    def test_init_success(self, config_with_nas):
        """Test successful initialization."""
        nas = NasManager(config_with_nas)
        assert nas.nas_root == Path(config_with_nas["nas"]["root"])

    def test_get_raw_path(self, config_with_nas):
        """Test getting raw path for a container."""
        nas = NasManager(config_with_nas)
        raw_path = nas.get_raw_path(1)
        path_str = str(raw_path).replace("\\", "/")
        assert path_str.endswith("01_RAW/containers/1")

    def test_get_work_path(self, config_with_nas):
        """Test getting work path for a container."""
        nas = NasManager(config_with_nas)
        work_path = nas.get_work_path(1)
        path_str = str(work_path).replace("\\", "/")
        assert path_str.endswith("02_WORK/containers/1")

    def test_get_logs_path(self, config_with_nas):
        """Test getting logs path."""
        nas = NasManager(config_with_nas)
        logs_path = nas.get_logs_path()
        assert str(logs_path).endswith("05_LOGS")

    def test_get_reference_path(self, config_with_nas):
        """Test getting reference path."""
        nas = NasManager(config_with_nas)
        ref_path = nas.get_reference_path()
        assert str(ref_path).endswith("03_REFERENCE")

    def test_get_publish_path(self, config_with_nas):
        """Test getting publish path."""
        nas = NasManager(config_with_nas)
        pub_path = nas.get_publish_path()
        assert str(pub_path).endswith("04_PUBLISH")

    def test_get_state_path(self, config_with_nas):
        """Test getting state path."""
        nas = NasManager(config_with_nas)
        state_path = nas.get_state_path()
        assert str(state_path).endswith("00_STATE")

    def test_is_accessible_existing_path(self, config_with_nas):
        """Test is_accessible returns True for existing readable path."""
        nas = NasManager(config_with_nas)
        assert nas.is_accessible(nas.get_logs_path())

    def test_is_accessible_nonexistent_path(self, config_with_nas):
        """Test is_accessible returns False for nonexistent path."""
        nas = NasManager(config_with_nas)
        assert not nas.is_accessible(Path("/nonexistent/path"))

    def test_is_writable_existing_path(self, config_with_nas):
        """Test is_writable returns True for existing writable path."""
        nas = NasManager(config_with_nas)
        assert nas.is_writable(nas.get_logs_path())

    def test_is_writable_nonexistent_path(self, config_with_nas):
        """Test is_writable returns False for nonexistent path."""
        nas = NasManager(config_with_nas)
        assert not nas.is_writable(Path("/nonexistent/path"))

    def test_is_writable_readonly_path(self, config_with_nas):
        """Test is_writable returns False for read-only path."""
        # Skip on Windows since permission model is different
        import sys
        if sys.platform == "win32":
            pytest.skip("Permission model differs on Windows")

        nas = NasManager(config_with_nas)
        logs_path = nas.get_logs_path()
        os.chmod(logs_path, 0o444)
        try:
            assert not nas.is_writable(logs_path)
        finally:
            os.chmod(logs_path, 0o755)

    def test_create_work_dir_success(self, config_with_nas):
        """Test successful work directory creation."""
        nas = NasManager(config_with_nas)
        work_path = nas.create_work_dir(999)
        assert work_path.exists()
        assert nas.is_writable(work_path)

    def test_create_work_dir_already_exists(self, config_with_nas):
        """Test create_work_dir when directory already exists."""
        nas = NasManager(config_with_nas)
        # Create once
        work_path1 = nas.create_work_dir(123)
        # Create again - should not raise
        work_path2 = nas.create_work_dir(123)
        assert work_path1 == work_path2

    def test_create_work_dir_permission_denied(self, config_with_nas):
        """Test create_work_dir when parent directory is not writable."""
        # Skip on Windows since permission model is different
        import sys
        if sys.platform == "win32":
            pytest.skip("Permission model differs on Windows")

        nas = NasManager(config_with_nas)
        work_dir = nas.nas_root / "02_WORK"
        os.chmod(work_dir, 0o000)
        try:
            with pytest.raises(NasError, match="Permission denied"):
                nas.create_work_dir(888)
        finally:
            os.chmod(work_dir, 0o755)

    def test_verify_all_paths(self, config_with_nas):
        """Test verification of all standard paths."""
        nas = NasManager(config_with_nas)
        results = nas.verify_all_paths()
        assert isinstance(results, dict)
        assert "00_STATE" in results
        assert "01_RAW" in results
        assert "02_WORK" in results
        assert "03_REFERENCE" in results
        assert "04_PUBLISH" in results
        assert "05_LOGS" in results
        # All should be accessible
        assert all(results.values())

    def test_verify_all_paths_missing_directory(self, temp_nas_root):
        """Test verification when a standard directory is missing."""
        config = {"nas": {"root": str(temp_nas_root)}}
        # Remove a directory
        (temp_nas_root / "03_REFERENCE").rmdir()
        nas = NasManager(config)
        results = nas.verify_all_paths()
        assert results["03_REFERENCE"] is False

    def test_path_construction_with_string_container_id(self, config_with_nas):
        """Test path construction accepts string container IDs."""
        nas = NasManager(config_with_nas)
        # Should handle integer
        path1 = nas.get_raw_path(123)
        # Should handle string
        path2 = nas.get_raw_path("123")
        assert path1 == path2
