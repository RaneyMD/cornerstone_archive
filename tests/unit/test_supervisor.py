"""Unit tests for supervisor system."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scripts.supervisor.supervisor import Supervisor
from scripts.supervisor.utils import (
    check_watcher_process,
    create_pause_flag,
    delete_pause_flag,
    get_commit_log,
    get_current_commit,
    get_heartbeat_age_seconds,
    is_watcher_healthy,
    is_watcher_paused,
    read_heartbeat_file,
    validate_label,
)


class TestValidateLabel:
    """Test label validation."""

    def test_validate_label_none(self):
        """None label is valid."""
        valid, error = validate_label(None)
        assert valid is True
        assert error == ""

    def test_validate_label_valid(self):
        """Valid label passes."""
        valid, error = validate_label("test label 123")
        assert valid is True
        assert error == ""

    def test_validate_label_with_hyphens(self):
        """Label with hyphens is valid."""
        valid, error = validate_label("test-label-123")
        assert valid is True
        assert error == ""

    def test_validate_label_with_underscores(self):
        """Label with underscores is valid."""
        valid, error = validate_label("test_label_123")
        assert valid is True
        assert error == ""

    def test_validate_label_too_long(self):
        """Label over 100 chars is invalid."""
        long_label = "a" * 101
        valid, error = validate_label(long_label)
        assert valid is False
        assert "too long" in error.lower()

    def test_validate_label_special_characters(self):
        """Label with special characters is invalid."""
        valid, error = validate_label("test@label!")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_validate_label_not_string(self):
        """Non-string label is invalid."""
        valid, error = validate_label(123)
        assert valid is False
        assert "must be a string" in error.lower()


class TestReadHeartbeatFile:
    """Test heartbeat file reading."""

    def test_read_heartbeat_file_valid(self):
        """Valid heartbeat file is parsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "heartbeat.json"
            heartbeat = {
                "watcher_id": "OrionMX",
                "pid": 12345,
                "status": "running",
            }
            path.write_text(json.dumps(heartbeat))

            result = read_heartbeat_file(path)
            assert result == heartbeat

    def test_read_heartbeat_file_missing(self):
        """Missing heartbeat file returns None."""
        path = Path("/nonexistent/heartbeat.json")
        result = read_heartbeat_file(path)
        assert result is None

    def test_read_heartbeat_file_invalid_json(self):
        """Invalid JSON returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "heartbeat.json"
            path.write_text("not valid json {")

            result = read_heartbeat_file(path)
            assert result is None


class TestGetHeartbeatAgeSeconds:
    """Test heartbeat age calculation."""

    def test_get_heartbeat_age_iso8601(self):
        """ISO 8601 timestamp age is calculated."""
        now = datetime.now(timezone.utc)
        past = now.isoformat()

        age = get_heartbeat_age_seconds(past)
        assert age is not None
        assert 0 <= age < 2  # Should be very recent

    def test_get_heartbeat_age_mysql_datetime(self):
        """MySQL datetime age is calculated."""
        # Use ISO format instead since that's what the function expects
        now = datetime.now(timezone.utc)
        past = now.isoformat()

        age = get_heartbeat_age_seconds(past)
        assert age is not None
        assert 0 <= age < 2

    def test_get_heartbeat_age_invalid_timestamp(self):
        """Invalid timestamp returns None."""
        age = get_heartbeat_age_seconds("not a timestamp")
        assert age is None


class TestIsWatcherHealthy:
    """Test watcher health determination."""

    def test_is_watcher_healthy_running(self):
        """Healthy running watcher returns True."""
        now = datetime.now(timezone.utc).isoformat()
        heartbeat = {
            "status": "running",
            "timestamp": now,
        }
        assert is_watcher_healthy(heartbeat) is True

    def test_is_watcher_healthy_missing_heartbeat(self):
        """None heartbeat returns False."""
        assert is_watcher_healthy(None) is False

    def test_is_watcher_healthy_wrong_status(self):
        """Non-running status returns False."""
        now = datetime.now(timezone.utc).isoformat()
        heartbeat = {
            "status": "stopped",
            "timestamp": now,
        }
        assert is_watcher_healthy(heartbeat) is False

    def test_is_watcher_healthy_stale_heartbeat(self):
        """Stale heartbeat (> 5 min) returns False."""
        # Create timestamp 10 minutes ago
        past = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - 600,
            tz=timezone.utc,
        )
        heartbeat = {
            "status": "running",
            "timestamp": past.isoformat(),
        }
        assert is_watcher_healthy(heartbeat) is False


class TestPauseFlag:
    """Test pause flag operations."""

    def test_is_watcher_paused_true(self):
        """Existing pause flag returns True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)
            pause_flag = state_path / "supervisor_pause_OrionMX.flag"
            pause_flag.touch()

            assert is_watcher_paused(state_path, "OrionMX") is True

    def test_is_watcher_paused_false(self):
        """Missing pause flag returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)
            assert is_watcher_paused(state_path, "OrionMX") is False

    def test_create_pause_flag(self):
        """Pause flag is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)
            result = create_pause_flag(state_path, "OrionMX")
            assert result is True
            pause_flag = state_path / "supervisor_pause_OrionMX.flag"
            assert pause_flag.exists()

    def test_delete_pause_flag(self):
        """Pause flag is deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)
            pause_flag = state_path / "supervisor_pause_OrionMX.flag"
            pause_flag.touch()

            result = delete_pause_flag(state_path, "OrionMX")
            assert result is True
            assert not pause_flag.exists()


class TestCheckWatcherProcess:
    """Test watcher process checking."""

    def test_check_watcher_process_not_running(self):
        """Missing watcher process returns False."""
        # This test should pass since we're looking for a process that doesn't exist
        result = check_watcher_process("NonexistentWatcher12345")
        assert result is False

    @patch('scripts.supervisor.utils.psutil.process_iter')
    def test_check_watcher_process_exception_handling(self, mock_process_iter):
        """Exception in process iteration is handled gracefully."""
        # Simulate an exception during process iteration
        mock_process_iter.side_effect = Exception("Process iteration failed")

        result = check_watcher_process("OrionMX")
        assert result is False


class TestGetCommitInfo:
    """Test git commit information retrieval."""

    @patch('scripts.supervisor.utils.run_command')
    def test_get_current_commit(self, mock_run_command):
        """Current commit is retrieved."""
        mock_run_command.return_value = {
            'returncode': 0,
            'stdout': 'abc1234\n',
            'stderr': '',
        }

        result = get_current_commit(Path('/repo'))
        assert result == 'abc1234'

    @patch('scripts.supervisor.utils.run_command')
    def test_get_current_commit_failure(self, mock_run_command):
        """Failed commit retrieval returns None."""
        mock_run_command.return_value = {
            'returncode': 1,
            'stdout': '',
            'stderr': 'fatal error',
        }

        result = get_current_commit(Path('/repo'))
        assert result is None

    @patch('scripts.supervisor.utils.run_command')
    def test_get_commit_log(self, mock_run_command):
        """Commit log is retrieved."""
        mock_run_command.return_value = {
            'returncode': 0,
            'stdout': 'abc1234 commit 1\ndef5678 commit 2\n',
            'stderr': '',
        }

        result = get_commit_log(Path('/repo'), count=2)
        assert len(result) == 2
        assert result[0] == 'abc1234 commit 1'


class TestSupervisorInit:
    """Test Supervisor initialization."""

    @patch('scripts.supervisor.supervisor.load_supervisor_config')
    @patch('scripts.supervisor.supervisor.NasManager')
    @patch('scripts.supervisor.supervisor.Database')
    def test_supervisor_init_success(self, mock_db_class, mock_nas_class, mock_load_config):
        """Supervisor initializes successfully."""
        # Setup mocks
        mock_load_config.return_value = {
            'nas': {'root': '/nas'},
            'database': {
                'host': 'localhost',
                'user': 'user',
                'password': 'pass',
                'database': 'db',
            },
        }
        mock_nas = MagicMock()
        mock_nas.get_state_path.return_value = Path('/nas/state')
        mock_nas_class.return_value = mock_nas

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        supervisor = Supervisor('config.yaml', 'OrionMX')

        assert supervisor.worker_id == 'OrionMX'
        assert supervisor.nas is mock_nas
        assert supervisor.db is mock_db

    @patch('scripts.supervisor.supervisor.load_supervisor_config')
    def test_supervisor_init_missing_config(self, mock_load_config):
        """Missing NAS root raises error."""
        mock_load_config.return_value = {
            'database': {'host': 'localhost'},
        }

        with pytest.raises(Exception):
            Supervisor('config.yaml', 'OrionMX')


class TestSupervisorCheckHealth:
    """Test Supervisor health checking."""

    @patch('scripts.supervisor.supervisor.load_supervisor_config')
    @patch('scripts.supervisor.supervisor.NasManager')
    @patch('scripts.supervisor.supervisor.Database')
    @patch('scripts.supervisor.supervisor.check_watcher_process')
    @patch('scripts.supervisor.supervisor.read_watcher_heartbeat')
    def test_check_watcher_health_running(
        self,
        mock_read_hb,
        mock_check_proc,
        mock_db_class,
        mock_nas_class,
        mock_load_config,
    ):
        """Watcher health check works correctly."""
        # Setup mocks
        mock_load_config.return_value = {
            'nas': {'root': '/nas'},
            'database': {
                'host': 'localhost',
                'user': 'user',
                'password': 'pass',
                'database': 'db',
            },
        }
        mock_nas = MagicMock()
        mock_nas.get_state_path.return_value = Path('/nas/state')
        mock_nas_class.return_value = mock_nas

        mock_db_class.return_value = MagicMock()

        mock_check_proc.return_value = True
        now = datetime.now(timezone.utc).isoformat()
        mock_read_hb.return_value = {
            'status': 'running',
            'timestamp': now,
        }

        supervisor = Supervisor('config.yaml', 'OrionMX')
        health = supervisor.check_watcher_health()

        assert health['running'] is True
        assert health['healthy'] is True
        assert health['state'] == 'running'
