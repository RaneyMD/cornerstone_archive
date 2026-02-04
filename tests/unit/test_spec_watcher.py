"""Unit tests for spec_watcher module."""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from scripts.watcher.spec_watcher import (
    Watcher,
    WatcherError,
    TaskClaimError,
    HandlerNotFoundError,
    TaskExecutionError,
    get_handler,
)


class TestWatcher:
    """Tests for Watcher class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return {
            "environment": "development",
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
            "nas": {"root": "/tmp/nas"},
            "logging": {"level": "INFO"},
            "watcher": {
                "scan_interval_seconds": 5,
                "heartbeat_interval_seconds": 30,
                "continuous_mode": False,
            },
        }

    @pytest.fixture
    def mock_nas(self):
        """Create mock NasManager."""
        nas = MagicMock()
        nas.get_logs_path.return_value = Path("/tmp/nas/05_LOGS")
        return nas

    @pytest.fixture
    def mock_db(self):
        """Create mock Database."""
        return MagicMock()

    @pytest.fixture
    def watcher(self, mock_config, mock_nas, mock_db):
        """Create Watcher instance."""
        return Watcher(mock_config, mock_nas, mock_db, worker_id="TestWorker")

    def test_init_success(self, mock_config, mock_nas, mock_db):
        """Test successful initialization."""
        watcher = Watcher(mock_config, mock_nas, mock_db, worker_id="TestWorker")
        assert watcher.worker_id == "TestWorker"
        assert watcher.running is True

    def test_scan_pending_tasks_empty(self, watcher, tmp_path):
        """Test scanning when no pending tasks."""
        pending_path = tmp_path / "05_LOGS" / "flags" / "pending"
        pending_path.mkdir(parents=True)
        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"

        tasks = watcher.scan_pending_tasks()
        assert tasks == []

    def test_scan_pending_tasks_found(self, watcher, tmp_path):
        """Test scanning finds pending tasks."""
        pending_path = tmp_path / "05_LOGS" / "flags" / "pending"
        pending_path.mkdir(parents=True)

        # Create task flag
        task_dict = {
            "task_id": "test_001",
            "container_id": 1,
            "handler": "acquire_source",
            "params": {"ia_identifier": "test_ia"},
        }
        with open(pending_path / "test_001.flag", "w") as f:
            json.dump(task_dict, f)

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"
        tasks = watcher.scan_pending_tasks()

        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "test_001"

    def test_scan_pending_tasks_invalid_json(self, watcher, tmp_path):
        """Test scanning handles invalid JSON gracefully."""
        pending_path = tmp_path / "05_LOGS" / "flags" / "pending"
        pending_path.mkdir(parents=True)

        # Create invalid JSON file
        with open(pending_path / "invalid.flag", "w") as f:
            f.write("invalid json {")

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"
        tasks = watcher.scan_pending_tasks()

        # Should skip invalid file and return empty list
        assert tasks == []

    def test_claim_task_success(self, watcher, tmp_path):
        """Test successful task claiming."""
        flags_path = tmp_path / "05_LOGS" / "flags"
        pending_path = flags_path / "pending"
        processing_path = flags_path / "processing"
        pending_path.mkdir(parents=True)
        processing_path.mkdir(parents=True)

        # Create pending task
        pending_file = pending_path / "test_001.flag"
        pending_file.write_text("{}")

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"

        # Claim task
        result = watcher.claim_task("test_001")

        assert result is True
        assert not pending_file.exists()
        assert (processing_path / "test_001.flag").exists()

    def test_claim_task_already_claimed(self, watcher, tmp_path):
        """Test claiming already-claimed task."""
        flags_path = tmp_path / "05_LOGS" / "flags"
        processing_path = flags_path / "processing"
        processing_path.mkdir(parents=True)

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"

        # Attempt to claim non-existent pending task
        result = watcher.claim_task("nonexistent")

        assert result is False

    def test_record_result_success(self, watcher, tmp_path):
        """Test recording successful task result."""
        flags_path = tmp_path / "05_LOGS" / "flags"
        processing_path = flags_path / "processing"
        completed_path = flags_path / "completed"
        processing_path.mkdir(parents=True)
        completed_path.mkdir(parents=True)

        # Create processing task
        (processing_path / "test_001.flag").write_text("{}")

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"

        task = {"task_id": "test_001"}
        result = {"status": "success", "pages": 42}

        watcher.record_result(task, result, success=True)

        # Flag should be moved to completed
        assert not (processing_path / "test_001.flag").exists()
        assert (completed_path / "test_001.flag").exists()
        assert (completed_path / "test_001.json").exists()

        # Check result file content
        with open(completed_path / "test_001.json") as f:
            result_data = json.load(f)
            assert result_data["task_id"] == "test_001"
            assert result_data["success"] is True
            assert result_data["result"]["status"] == "success"

    def test_record_result_failure(self, watcher, tmp_path):
        """Test recording failed task result."""
        flags_path = tmp_path / "05_LOGS" / "flags"
        processing_path = flags_path / "processing"
        failed_path = flags_path / "failed"
        processing_path.mkdir(parents=True)
        failed_path.mkdir(parents=True)

        # Create processing task
        (processing_path / "test_001.flag").write_text("{}")

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"

        task = {"task_id": "test_001"}
        result = {"error": "Download failed"}

        watcher.record_result(task, result, success=False)

        # Flag should be moved to failed
        assert not (processing_path / "test_001.flag").exists()
        assert (failed_path / "test_001.flag").exists()
        assert (failed_path / "test_001.json").exists()

    def test_report_heartbeat(self, watcher, mock_db):
        """Test heartbeat reporting to database."""
        watcher.scan_pending_tasks = Mock(return_value=[])

        watcher.report_heartbeat()

        # Verify database was called
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "workers_t" in call_args[0][0]
        assert "TestWorker" in call_args[0][1]

    def test_execute_handler_success(self, watcher):
        """Test successful handler execution."""
        mock_handler = Mock(return_value={"status": "success"})

        with patch("scripts.watcher.spec_watcher.get_handler", return_value=mock_handler):
            task = {
                "task_id": "test_001",
                "handler": "test_handler",
                "params": {"key": "value"},
            }

            result = watcher.execute_handler(task)

            assert result["status"] == "success"
            mock_handler.assert_called_once()

    def test_execute_handler_not_found(self, watcher):
        """Test execution with unknown handler."""
        with patch("scripts.watcher.spec_watcher.get_handler", return_value=None):
            task = {"task_id": "test_001", "handler": "nonexistent"}

            with pytest.raises(HandlerNotFoundError):
                watcher.execute_handler(task)

    def test_execute_handler_no_handler_specified(self, watcher):
        """Test execution with no handler specified."""
        task = {"task_id": "test_001"}

        with pytest.raises(TaskExecutionError):
            watcher.execute_handler(task)


class TestGetHandler:
    """Tests for get_handler function."""

    def test_get_handler_acquire_source(self):
        """Test getting acquire_source handler."""
        handler = get_handler("acquire_source")
        assert handler is not None
        assert callable(handler)

    def test_get_handler_unknown(self):
        """Test getting unknown handler."""
        handler = get_handler("nonexistent_handler")
        assert handler is None

    def test_get_handler_import_error(self):
        """Test handling import errors gracefully."""
        with patch("scripts.watcher.spec_watcher.get_handler") as mock_get:
            mock_get.return_value = None
            handler = get_handler("failing_handler")
            assert handler is None


class TestWatcherSignalHandling:
    """Tests for signal handling."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return {
            "environment": "development",
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
            "nas": {"root": "/tmp/nas"},
            "logging": {"level": "INFO"},
            "watcher": {
                "scan_interval_seconds": 5,
                "heartbeat_interval_seconds": 30,
            },
        }

    @pytest.fixture
    def mock_nas(self):
        """Create mock NasManager."""
        nas = MagicMock()
        nas.get_logs_path.return_value = Path("/tmp/nas/05_LOGS")
        return nas

    @pytest.fixture
    def mock_db(self):
        """Create mock Database."""
        return MagicMock()

    def test_handle_shutdown(self, mock_config, mock_nas, mock_db):
        """Test graceful shutdown signal handling."""
        watcher = Watcher(mock_config, mock_nas, mock_db)
        assert watcher.running is True

        # Simulate SIGTERM
        watcher.handle_shutdown(15, None)

        assert watcher.running is False
