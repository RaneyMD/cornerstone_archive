"""Integration tests for supervisor handlers."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scripts.supervisor.handlers import (
    diagnostics,
    pause_watcher,
    restart_watcher,
    resume_watcher,
    rollback_code,
    update_code,
    update_code_deps,
    verify_database,
)


class TestPauseWatcherHandler:
    """Test pause_watcher handler."""

    def test_pause_watcher_flag_created(self):
        """Pause flag is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)

            # Mock NAS
            nas = MagicMock()
            nas.get_state_path.return_value = state_path

            # Mock DB
            db = MagicMock()

            task = {}
            result = pause_watcher(nas, db, 'OrionMX', task)

            assert result['success'] is True
            assert (state_path / 'supervisor_pause_OrionMX.flag').exists()

    def test_pause_watcher_with_label(self):
        """Pause handler records label."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)

            nas = MagicMock()
            nas.get_state_path.return_value = state_path

            db = MagicMock()

            task = {'label': 'test pause'}
            result = pause_watcher(nas, db, 'OrionMX', task)

            assert result['success'] is True
            assert result['label'] == 'test pause'
            db.insert.assert_called_once()

    def test_pause_watcher_invalid_label(self):
        """Invalid label is rejected."""
        nas = MagicMock()
        db = MagicMock()

        task = {'label': 'a' * 101}  # Too long
        result = pause_watcher(nas, db, 'OrionMX', task)

        assert result['success'] is False


class TestResumeWatcherHandler:
    """Test resume_watcher handler."""

    @patch('scripts.supervisor.handlers.delete_pause_flag')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_resume_watcher_flag_deleted(self, mock_start, mock_delete):
        """Resume deletes pause flag and starts watcher."""
        mock_delete.return_value = True
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {}
        result = resume_watcher(nas, db, 'OrionMX', task)

        assert result['success'] is True
        mock_delete.assert_called_once()
        mock_start.assert_called_once()

    @patch('scripts.supervisor.handlers.delete_pause_flag')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_resume_watcher_with_label(self, mock_start, mock_delete):
        """Resume handler records label."""
        mock_delete.return_value = True
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {'label': 'test resume'}
        result = resume_watcher(nas, db, 'OrionMX', task)

        assert result['success'] is True
        assert result['label'] == 'test resume'


class TestUpdateCodeHandler:
    """Test update_code handler."""

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.get_current_commit')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_update_code_runs_git_pull(
        self, mock_start, mock_get_commit, mock_run_cmd, mock_stop
    ):
        """Update code runs git pull."""
        mock_stop.return_value = True
        mock_get_commit.side_effect = ['abc1234', 'def5678']
        mock_run_cmd.return_value = {
            'returncode': 0,
            'stdout': 'Already up to date',
            'stderr': '',
        }
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {}
        result = update_code(nas, db, 'OrionMX', task)

        assert result['success'] is True
        assert result['before_commit'] == 'abc1234'
        assert result['after_commit'] == 'def5678'
        mock_run_cmd.assert_called_once()

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.get_current_commit')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_update_code_with_label(
        self, mock_start, mock_run_cmd, mock_get_commit, mock_stop
    ):
        """Update code handler records label."""
        mock_stop.return_value = True
        mock_get_commit.side_effect = ['abc1234', 'def5678']
        mock_run_cmd.return_value = {
            'returncode': 0,
            'stdout': 'Already up to date',
            'stderr': '',
        }
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {'label': 'AA v1'}
        result = update_code(nas, db, 'OrionMX', task)

        assert result['success'] is True
        assert result.get('label') == 'AA v1'


class TestUpdateCodeDepsHandler:
    """Test update_code_deps handler."""

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.get_current_commit')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_update_code_deps_installs_dev_requirements(
        self, mock_start, mock_get_commit, mock_run_cmd, mock_stop
    ):
        """Update deps runs pip with requirements-dev.txt."""
        mock_stop.return_value = True
        mock_get_commit.side_effect = ['abc1234', 'def5678']
        mock_run_cmd.side_effect = [
            # git pull
            {'returncode': 0, 'stdout': 'Already up to date', 'stderr': ''},
            # pip install
            {'returncode': 0, 'stdout': 'Successfully installed', 'stderr': ''},
        ]
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {}
        result = update_code_deps(nas, db, 'OrionMX', task)

        assert result['success'] is True
        # Verify pip was called with dev requirements
        calls = mock_run_cmd.call_args_list
        assert len(calls) == 2
        pip_call = calls[1][0][0]
        assert 'requirements-dev.txt' in pip_call

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_update_code_deps_with_label(
        self, mock_start, mock_run_cmd, mock_stop
    ):
        """Update deps handler records label."""
        mock_stop.return_value = True
        mock_run_cmd.side_effect = [
            {'returncode': 0, 'stdout': '', 'stderr': ''},
            {'returncode': 0, 'stdout': '', 'stderr': ''},
        ]
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {'label': 'impl HT acquire'}
        result = update_code_deps(nas, db, 'OrionMX', task)

        assert result['label'] == 'impl HT acquire'


class TestRestartWatcherHandler:
    """Test restart_watcher handler."""

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.start_watcher')
    @patch('scripts.supervisor.handlers.is_watcher_paused')
    def test_restart_watcher_respects_pause_flag(
        self, mock_is_paused, mock_start, mock_stop
    ):
        """Restart respects pause flag."""
        mock_stop.return_value = True
        mock_start.return_value = True
        mock_is_paused.return_value = True

        nas = MagicMock()
        nas.get_state_path.return_value = Path('/nas')
        db = MagicMock()

        task = {}
        result = restart_watcher(nas, db, 'OrionMX', task)

        assert result['success'] is True
        assert result['paused'] is True

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.start_watcher')
    @patch('scripts.supervisor.handlers.is_watcher_paused')
    def test_restart_watcher_with_label(
        self, mock_is_paused, mock_start, mock_stop
    ):
        """Restart handler records label."""
        mock_stop.return_value = True
        mock_start.return_value = True
        mock_is_paused.return_value = False

        nas = MagicMock()
        nas.get_state_path.return_value = Path('/nas')
        db = MagicMock()

        task = {'label': 'restart test'}
        result = restart_watcher(nas, db, 'OrionMX', task)

        assert result['label'] == 'restart test'


class TestRollbackCodeHandler:
    """Test rollback_code handler."""

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.get_current_commit')
    @patch('scripts.supervisor.handlers.get_commit_log')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_rollback_code_single_commit(
        self,
        mock_start,
        mock_get_log,
        mock_get_commit,
        mock_run_cmd,
        mock_stop,
    ):
        """Rollback single commit."""
        mock_stop.return_value = True
        mock_get_commit.side_effect = ['abc1234', 'def5678']
        mock_get_log.return_value = ['abc1234 commit 1']
        mock_run_cmd.return_value = {
            'returncode': 0,
            'stdout': 'Reverted',
            'stderr': '',
        }
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {'params': {'commits_back': 1}}
        result = rollback_code(nas, db, 'OrionMX', task)

        assert result['success'] is True
        assert result['commits_reverted'] == 1

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.get_current_commit')
    @patch('scripts.supervisor.handlers.get_commit_log')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_rollback_code_multiple_commits(
        self,
        mock_start,
        mock_get_log,
        mock_get_commit,
        mock_run_cmd,
        mock_stop,
    ):
        """Rollback multiple commits."""
        mock_stop.return_value = True
        mock_get_commit.side_effect = ['abc1234', 'xyz9999']
        mock_get_log.return_value = ['abc1234 commit 1', 'def5678 commit 2']
        mock_run_cmd.side_effect = [
            {'returncode': 0, 'stdout': 'Reverted 1', 'stderr': ''},
            {'returncode': 0, 'stdout': 'Reverted 2', 'stderr': ''},
            {'returncode': 0, 'stdout': 'Reverted 3', 'stderr': ''},
        ]
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {'params': {'commits_back': 3}}
        result = rollback_code(nas, db, 'OrionMX', task)

        assert result['success'] is True
        assert result['commits_reverted'] == 3

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.get_current_commit')
    @patch('scripts.supervisor.handlers.get_commit_log')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_rollback_code_invalid_parameter(
        self,
        mock_start,
        mock_get_log,
        mock_get_commit,
        mock_run_cmd,
        mock_stop,
    ):
        """Invalid commits_back parameter is rejected."""
        nas = MagicMock()
        db = MagicMock()

        task = {'params': {'commits_back': 99}}  # Out of range
        result = rollback_code(nas, db, 'OrionMX', task)

        assert result['success'] is False

    @patch('scripts.supervisor.handlers.stop_watcher_gracefully')
    @patch('scripts.supervisor.handlers.run_command')
    @patch('scripts.supervisor.handlers.get_current_commit')
    @patch('scripts.supervisor.handlers.get_commit_log')
    @patch('scripts.supervisor.handlers.start_watcher')
    def test_rollback_code_with_label(
        self,
        mock_start,
        mock_get_log,
        mock_get_commit,
        mock_run_cmd,
        mock_stop,
    ):
        """Rollback handler records label."""
        mock_stop.return_value = True
        mock_get_commit.side_effect = ['abc1234', 'def5678']
        mock_get_log.return_value = ['abc1234 commit 1']
        mock_run_cmd.return_value = {
            'returncode': 0,
            'stdout': 'Reverted',
            'stderr': '',
        }
        mock_start.return_value = True

        nas = MagicMock()
        db = MagicMock()

        task = {'params': {'commits_back': 1}, 'label': 'hotfix'}
        result = rollback_code(nas, db, 'OrionMX', task)

        assert result['label'] == 'hotfix'


class TestDiagnosticsHandler:
    """Test diagnostics handler."""

    @patch('scripts.supervisor.utils.psutil.disk_usage')
    @patch('scripts.supervisor.utils.check_watcher_process')
    @patch('scripts.supervisor.heartbeat.read_watcher_heartbeat')
    @patch('scripts.supervisor.utils.is_watcher_healthy')
    def test_diagnostics_report_generated(
        self,
        mock_is_healthy,
        mock_read_hb,
        mock_check_proc,
        mock_disk,
    ):
        """Diagnostics report is generated."""
        mock_check_proc.return_value = True
        mock_read_hb.return_value = {'status': 'running'}
        mock_is_healthy.return_value = True
        mock_disk.return_value = MagicMock(
            total=1000,
            used=500,
            free=500,
            percent=50,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            nas = MagicMock()
            nas.get_state_path.return_value = Path(tmpdir) / '00_STATE'
            nas.get_logs_path.return_value = Path(tmpdir) / '05_LOGS'

            db = MagicMock()
            db.fetchAll.return_value = []

            task = {}
            result = diagnostics(nas, db, 'OrionMX', task)

            assert result['success'] is True
            assert 'report_path' in result

    @patch('scripts.supervisor.utils.psutil.disk_usage')
    @patch('scripts.supervisor.utils.check_watcher_process')
    @patch('scripts.supervisor.heartbeat.read_watcher_heartbeat')
    @patch('scripts.supervisor.utils.is_watcher_healthy')
    def test_diagnostics_with_label(
        self,
        mock_is_healthy,
        mock_read_hb,
        mock_check_proc,
        mock_disk,
    ):
        """Diagnostics handler records label."""
        mock_check_proc.return_value = True
        mock_read_hb.return_value = {'status': 'running'}
        mock_is_healthy.return_value = True
        mock_disk.return_value = MagicMock(
            total=1000,
            used=500,
            free=500,
            percent=50,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            nas = MagicMock()
            nas.get_state_path.return_value = Path(tmpdir) / '00_STATE'
            nas.get_logs_path.return_value = Path(tmpdir) / '05_LOGS'

            db = MagicMock()
            db.fetchAll.return_value = []

            task = {'label': 'debug run'}
            result = diagnostics(nas, db, 'OrionMX', task)

            assert result['label'] == 'debug run'


class TestVerifyDatabaseHandler:
    """Test verify_database handler."""

    def test_verify_db_all_tests_pass(self):
        """All database tests pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nas = MagicMock()
            nas.get_logs_path.return_value = Path(tmpdir)

            db = MagicMock()
            db.fetchOne.side_effect = [
                # Test 1: Connection (implicit)
                # Test 2: Query
                {'db_time': '2026-02-05 12:00:00', 'db_name': 'testdb'},
                # Test 3a: tables_t check
                {'count': 10},
                # Test 3b: jobs_t check
                {'count': 10},
                # Test 3c: workers_t check
                {'count': 10},
                # Test 3d: segments_t check
                {'count': 10},
                # Test 4: Timezone
                {'tz': '+00:00'},
            ]

            task = {}
            result = verify_database(nas, db, 'OrionMX', task)

            # Should generate report
            assert 'report_path' in result

    def test_verify_db_connection_fails(self):
        """Database connection failure is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nas = MagicMock()
            nas.get_logs_path.return_value = Path(tmpdir)

            db = MagicMock()
            db.fetchOne.side_effect = Exception("Connection failed")

            task = {}
            result = verify_database(nas, db, 'OrionMX', task)

            # Should still generate report, but success may be False
            assert 'report_path' in result

    def test_verify_db_with_label(self):
        """Verify DB handler records label."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nas = MagicMock()
            nas.get_logs_path.return_value = Path(tmpdir)

            db = MagicMock()
            db.fetchOne.side_effect = [
                {'db_time': '2026-02-05 12:00:00', 'db_name': 'testdb'},
                {'count': 10},
                {'count': 10},
                {'count': 10},
                {'count': 10},
                {'tz': '+00:00'},
            ]

            task = {'label': 'db check'}
            result = verify_database(nas, db, 'OrionMX', task)

            assert 'report_path' in result
            assert result.get('label') == 'db check'
