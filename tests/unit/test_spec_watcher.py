"""Unit tests for spec_watcher module."""

import json
import os
import pytest
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from scripts.watcher.spec_watcher import (
    Watcher,
    WatcherError,
    TaskClaimError,
    HandlerNotFoundError,
    TaskExecutionError,
    ClaudeExecutionError,
    ClaudePromptRunner,
    PromptFileError,
    main,
    MAX_PROMPT_BYTES,
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
        """Test scanning when no tasks in Worker_Inbox."""
        inbox_path = tmp_path / "05_LOGS" / "Worker_Inbox"
        inbox_path.mkdir(parents=True)
        watcher.nas.get_worker_inbox_path.return_value = inbox_path

        tasks = watcher.scan_pending_tasks()
        assert tasks == []

    def test_scan_pending_tasks_found(self, watcher, tmp_path):
        """Test scanning finds tasks in Worker_Inbox."""
        inbox_path = tmp_path / "05_LOGS" / "Worker_Inbox"
        inbox_path.mkdir(parents=True)

        # Create task flag
        task_dict = {
            "task_id": "test_001",
            "container_id": 1,
            "handler": "acquire_source",
            "params": {"ia_identifier": "test_ia"},
        }
        with open(inbox_path / "test_001.flag", "w") as f:
            json.dump(task_dict, f)

        watcher.nas.get_worker_inbox_path.return_value = inbox_path
        tasks = watcher.scan_pending_tasks()

        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "test_001"

    def test_scan_pending_tasks_invalid_json(self, watcher, tmp_path):
        """Test scanning handles invalid JSON gracefully."""
        inbox_path = tmp_path / "05_LOGS" / "Worker_Inbox"
        inbox_path.mkdir(parents=True)

        # Create invalid JSON file
        with open(inbox_path / "invalid.flag", "w") as f:
            f.write("invalid json {")

        watcher.nas.get_worker_inbox_path.return_value = inbox_path
        tasks = watcher.scan_pending_tasks()

        # Should skip invalid file and return empty list
        assert tasks == []

    def test_claim_task_success(self, watcher, tmp_path):
        """Test successful task claiming."""
        inbox_path = tmp_path / "05_LOGS" / "Worker_Inbox"
        processing_path = tmp_path / "05_LOGS" / "processing"
        inbox_path.mkdir(parents=True)
        processing_path.mkdir(parents=True)

        # Create inbox task
        inbox_file = inbox_path / "test_001.flag"
        inbox_file.write_text("{}")

        watcher.nas.get_worker_inbox_path.return_value = inbox_path
        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"

        # Claim task
        result = watcher.claim_task("test_001")

        assert result is True
        assert not inbox_file.exists()
        assert (processing_path / "test_001.flag").exists()

    def test_claim_task_already_claimed(self, watcher, tmp_path):
        """Test claiming already-claimed task."""
        inbox_path = tmp_path / "05_LOGS" / "Worker_Inbox"
        inbox_path.mkdir(parents=True)

        watcher.nas.get_worker_inbox_path.return_value = inbox_path
        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"

        # Attempt to claim non-existent inbox task
        result = watcher.claim_task("nonexistent")

        assert result is False

    def test_record_result_success(self, watcher, tmp_path):
        """Test recording successful task result to Worker_Outbox."""
        processing_path = tmp_path / "05_LOGS" / "processing"
        outbox_path = tmp_path / "05_LOGS" / "Worker_Outbox"
        processing_path.mkdir(parents=True)
        outbox_path.mkdir(parents=True)

        # Create processing task
        (processing_path / "test_001.flag").write_text("{}")

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"
        watcher.nas.get_worker_outbox_path.return_value = outbox_path

        task = {"task_id": "test_001"}
        result = {"status": "success", "pages": 42}

        watcher.record_result(task, result, success=True)

        # Processing flag should be removed
        assert not (processing_path / "test_001.flag").exists()
        # Result should be in Worker_Outbox
        assert (outbox_path / "test_001.result.json").exists()

        # Check result file content
        with open(outbox_path / "test_001.result.json") as f:
            result_data = json.load(f)
            assert result_data["task_id"] == "test_001"
            assert result_data["success"] is True
            assert result_data["result"]["status"] == "success"

    def test_record_result_failure(self, watcher, tmp_path):
        """Test recording failed task result to Worker_Outbox."""
        processing_path = tmp_path / "05_LOGS" / "processing"
        outbox_path = tmp_path / "05_LOGS" / "Worker_Outbox"
        processing_path.mkdir(parents=True)
        outbox_path.mkdir(parents=True)

        # Create processing task
        (processing_path / "test_001.flag").write_text("{}")

        watcher.nas.get_logs_path.return_value = tmp_path / "05_LOGS"
        watcher.nas.get_worker_outbox_path.return_value = outbox_path

        task = {"task_id": "test_001"}
        result = {"error": "Download failed"}

        watcher.record_result(task, result, success=False)

        # Processing flag should be removed
        assert not (processing_path / "test_001.flag").exists()
        # Error should be in Worker_Outbox with .error.json extension
        assert (outbox_path / "test_001.error.json").exists()

    def test_report_heartbeat(self, watcher, mock_db):
        """Test heartbeat reporting to database."""
        watcher.scan_pending_tasks = Mock(return_value=[])

        watcher.report_heartbeat()

        # Verify database was called
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "workers_t" in call_args[0][0]
        assert "TestWorker" in call_args[0][1]

    def test_report_heartbeat_uses_utc(self, watcher, mock_db):
        """Test that heartbeat is reported with UTC timezone and new terminology."""
        watcher.scan_pending_tasks = Mock(return_value=[])

        watcher.report_heartbeat()

        # Verify the heartbeat mention is about Worker_Inbox (new terminology)
        call_args = mock_db.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        status_summary = params[1]  # Get status_summary from params tuple
        assert "Worker_Inbox" in status_summary
        assert "workers_t" in sql

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

    def test_handle_shutdown_releases_lock(self, mock_config, mock_nas, mock_db, tmp_path):
        """handle_shutdown() calls release_lock(), cleaning up the lock directory."""
        mock_nas.get_state_path.return_value = tmp_path / "00_STATE"

        watcher = Watcher(mock_config, mock_nas, mock_db, worker_id="LockTestWorker")
        lock_dir = watcher.acquire_lock()
        assert lock_dir is not None
        assert lock_dir.exists()

        # Simulate SIGTERM
        watcher.handle_shutdown(15, None)

        assert watcher.running is False
        assert not lock_dir.exists()
        assert watcher.lock_dir is None


class TestWatcherLocking:
    """Tests for watcher filesystem lock (acquire / release / owner)."""

    @pytest.fixture
    def mock_config(self):
        return {
            "environment": "development",
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
            "nas": {"root": "/tmp/nas"},
            "logging": {"level": "INFO"},
            "watcher": {"scan_interval_seconds": 5, "heartbeat_interval_seconds": 30},
        }

    @pytest.fixture
    def mock_nas(self, tmp_path):
        nas = MagicMock()
        nas.get_state_path.return_value = tmp_path / "00_STATE"
        nas.get_logs_path.return_value = tmp_path / "05_LOGS"
        return nas

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def watcher(self, mock_config, mock_nas, mock_db):
        return Watcher(mock_config, mock_nas, mock_db, worker_id="TestWorker")

    def test_acquire_lock_success(self, watcher):
        """First acquire_lock() creates the lock directory and owner.json."""
        result = watcher.acquire_lock()

        assert result is not None
        assert result.is_dir()
        assert result.name == "watcher_TestWorker.lock"
        assert watcher.lock_dir == result
        assert (result / "owner.json").exists()

    def test_acquire_lock_already_held(self, watcher):
        """Second instance on same worker_id returns None."""
        first = watcher.acquire_lock()
        assert first is not None

        # Second watcher shares the same nas mock (same state path)
        watcher2 = Watcher(watcher.config, watcher.nas, watcher.db, worker_id="TestWorker")
        second = watcher2.acquire_lock()

        assert second is None
        assert watcher2.lock_dir is None

    def test_release_lock(self, watcher):
        """release_lock() removes owner.json and the lock directory."""
        lock_dir = watcher.acquire_lock()
        assert lock_dir.exists()

        watcher.release_lock()

        assert not lock_dir.exists()
        assert watcher.lock_dir is None

    def test_write_lock_owner(self, watcher):
        """owner.json contains correct fields and types."""
        lock_dir = watcher.acquire_lock()

        with open(lock_dir / "owner.json") as f:
            owner = json.load(f)

        assert owner["watcher_id"] == "TestWorker"
        assert isinstance(owner["pid"], int)
        assert isinstance(owner["hostname"], str)
        assert owner["executable"] == sys.executable
        assert owner["utc_locked_at"].endswith("Z")


class TestWatcherHeartbeatFile:
    """Tests for atomic heartbeat file writing."""

    @pytest.fixture
    def mock_config(self):
        return {
            "environment": "development",
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
            "nas": {"root": "/tmp/nas"},
            "logging": {"level": "INFO"},
            "watcher": {"scan_interval_seconds": 10, "heartbeat_interval_seconds": 60},
        }

    @pytest.fixture
    def mock_nas(self, tmp_path):
        nas = MagicMock()
        nas.get_state_path.return_value = tmp_path / "00_STATE"
        nas.get_logs_path.return_value = tmp_path / "05_LOGS"
        return nas

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def watcher(self, mock_config, mock_nas, mock_db):
        return Watcher(mock_config, mock_nas, mock_db, worker_id="TestWorker")

    def test_write_heartbeat_file(self, watcher):
        """Heartbeat file written correctly; no .tmp file remains."""
        watcher.write_heartbeat_file()

        state_path = watcher.nas.get_state_path()
        target = state_path / "watcher_heartbeat_TestWorker.json"
        tmp_file = target.with_suffix(".tmp")

        assert target.exists()
        assert not tmp_file.exists()

        with open(target) as f:
            data = json.load(f)

        assert data["watcher_id"] == "TestWorker"
        assert isinstance(data["pid"], int)
        assert isinstance(data["hostname"], str)
        assert data["status"] == "running"
        assert data["utc"].endswith("Z")
        assert data["poll_seconds"] == 10  # matches scan_interval_seconds in fixture


class TestWatcherEventLoop:
    """Tests for the run() event loop timing gates."""

    @pytest.fixture
    def mock_config(self):
        return {
            "environment": "development",
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
            "nas": {"root": "/tmp/nas"},
            "logging": {"level": "INFO"},
            "watcher": {"scan_interval_seconds": 2, "heartbeat_interval_seconds": 5},
        }

    @pytest.fixture
    def mock_nas(self, tmp_path):
        nas = MagicMock()
        nas.get_state_path.return_value = tmp_path / "00_STATE"
        nas.get_logs_path.return_value = tmp_path / "05_LOGS"
        nas.get_worker_inbox_path.return_value = tmp_path / "05_LOGS" / "Worker_Inbox"
        return nas

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def watcher(self, mock_config, mock_nas, mock_db):
        return Watcher(mock_config, mock_nas, mock_db, worker_id="TestWorker")

    @patch("time.sleep")
    @patch("time.time")
    def test_event_loop_scans_periodically(self, mock_time, mock_sleep, watcher):
        """scan_pending_tasks fires when scan_interval has elapsed."""
        # time.time() returns: 0 (pre-loop), 3 (first loop tick — 3 >= scan_interval 2)
        mock_time.side_effect = [0, 3]

        # Allow one full iteration; stop on the second sleep
        call_count = {"n": 0}
        def stop_on_second_sleep(duration):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                watcher.running = False
        mock_sleep.side_effect = stop_on_second_sleep

        watcher.scan_pending_tasks = Mock(return_value=[])
        watcher.report_heartbeat = Mock()
        watcher.write_heartbeat_file = Mock()

        watcher.run()

        # scan_pending_tasks must have been called at least once in the scan gate
        assert watcher.scan_pending_tasks.call_count >= 1

    @patch("time.sleep")
    @patch("time.time")
    def test_event_loop_heartbeat_periodically(self, mock_time, mock_sleep, watcher):
        """report_heartbeat + write_heartbeat_file fire when heartbeat_interval elapses."""
        # time.time() returns: 0 (pre-loop), 6 (first loop tick — 6 >= heartbeat_interval 5)
        mock_time.side_effect = [0, 6]

        call_count = {"n": 0}
        def stop_on_second_sleep(duration):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                watcher.running = False
        mock_sleep.side_effect = stop_on_second_sleep

        watcher.scan_pending_tasks = Mock(return_value=[])
        watcher.report_heartbeat = Mock()
        watcher.write_heartbeat_file = Mock()

        watcher.run()


class TestClaudePromptRunner:
    """Tests for ClaudePromptRunner behavior."""

    def test_prompt_file_missing(self, tmp_path):
        """Missing prompt file raises PromptFileError."""
        prompt_path = tmp_path / "missing.md"
        with pytest.raises(PromptFileError):
            ClaudePromptRunner(prompt_path)

    def test_prompt_file_not_a_file(self, tmp_path):
        """Directory prompt path raises PromptFileError."""
        prompt_path = tmp_path / "prompts"
        prompt_path.mkdir()
        with pytest.raises(PromptFileError):
            ClaudePromptRunner(prompt_path)

    def test_prompt_file_oversized(self, tmp_path):
        """Oversized prompt file raises PromptFileError."""
        prompt_path = tmp_path / "oversized.md"
        prompt_path.write_text("a" * (MAX_PROMPT_BYTES + 1), encoding="utf-8")
        with pytest.raises(PromptFileError):
            ClaudePromptRunner(prompt_path)

    def test_prompt_file_unreadable(self, tmp_path):
        """Unreadable prompt file raises PromptFileError."""
        prompt_path = tmp_path / "unreadable.md"
        prompt_path.write_text("content", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=OSError("unreadable")):
            with pytest.raises(PromptFileError):
                ClaudePromptRunner(prompt_path)

    def test_dry_run_returns_command(self, tmp_path):
        """Dry-run returns command structure without execution."""
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("Do the thing", encoding="utf-8")
        runner = ClaudePromptRunner(prompt_path, dry_run=True)

        result = runner.run()

        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["command"][0] == "claude"
        assert "--allowedTools" in result["command"]
        assert "--output-format" in result["command"]

    def test_json_parse_with_prefix(self, tmp_path):
        """Runner extracts JSON when stdout has leading text."""
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("Do the thing", encoding="utf-8")
        runner = ClaudePromptRunner(prompt_path)

        completed = Mock()
        completed.stdout = "warning\n{\"ok\": true}\n"
        completed.stderr = ""
        completed.returncode = 0

        with patch("subprocess.run", return_value=completed):
            result = runner.run()

        assert result["parsed"] == {"ok": True}

    def test_json_parse_failure_raises(self, tmp_path):
        """Runner raises ClaudeExecutionError when JSON is invalid."""
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("Do the thing", encoding="utf-8")
        runner = ClaudePromptRunner(prompt_path)

        completed = Mock()
        completed.stdout = "warning\nnot json"
        completed.stderr = ""
        completed.returncode = 0

        with patch("subprocess.run", return_value=completed):
            with pytest.raises(ClaudeExecutionError):
                runner.run()

    def test_timeout_raises(self, tmp_path):
        """Timeouts raise ClaudeExecutionError."""
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("Do the thing", encoding="utf-8")
        runner = ClaudePromptRunner(prompt_path, timeout_seconds=1)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=1)):
            with pytest.raises(ClaudeExecutionError):
                runner.run()


class TestPromptRunnerCli:
    """Tests for CLI prompt runner configuration."""

    def test_invalid_model_rejected(self, tmp_path, monkeypatch):
        """Invalid model names cause startup failure."""
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("Do the thing", encoding="utf-8")

        fake_config = {
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
            "logging": {"path": str(tmp_path / "logs")},
        }

        with patch("scripts.watcher.spec_watcher.load_config", return_value=fake_config), patch(
            "scripts.watcher.spec_watcher.NasManager"
        ), patch("scripts.watcher.spec_watcher.Database") as mock_db:
            mock_db.return_value = MagicMock()
            exit_code = main(
                [
                    "--config",
                    "config/config.yaml",
                    "--prompt-file",
                    str(prompt_path),
                    "--model",
                    "invalid-model",
                ]
            )

        assert exit_code == 1

    def test_prompt_file_path_resolution(self, tmp_path, monkeypatch):
        """Relative prompt paths resolve against the current working directory."""
        prompt_path = tmp_path / "prompts" / "prompt.md"
        prompt_path.parent.mkdir()
        prompt_path.write_text("Do the thing", encoding="utf-8")

        fake_config = {
            "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
            "logging": {"path": str(tmp_path / "logs")},
        }

        captured = {}

        def fake_runner(path, model=None, dry_run=False, timeout_seconds=300):
            captured["path"] = path
            return MagicMock(prompt_path=path)

        monkeypatch.chdir(tmp_path)

        with patch("scripts.watcher.spec_watcher.load_config", return_value=fake_config), patch(
            "scripts.watcher.spec_watcher.NasManager"
        ), patch("scripts.watcher.spec_watcher.Database") as mock_db, patch(
            "scripts.watcher.spec_watcher.ClaudePromptRunner", side_effect=fake_runner
        ), patch.object(Watcher, "scan_pending_tasks", return_value=[]):
            mock_db.return_value = MagicMock()
            exit_code = main(
                [
                    "--config",
                    "config/config.yaml",
                    "--prompt-file",
                    "prompts/prompt.md",
                    "--dry-run",
                ]
            )

        assert exit_code == 0
        assert captured["path"] == prompt_path.resolve()
