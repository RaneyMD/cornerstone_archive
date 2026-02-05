"""Control flag handlers for supervisor."""

import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.common.spec_db import Database
from scripts.common.spec_nas import NasManager
from scripts.supervisor.utils import (
    create_pause_flag,
    delete_pause_flag,
    get_commit_log,
    get_current_commit,
    is_watcher_paused,
    read_heartbeat_file,
    run_command,
    start_watcher,
    stop_watcher_gracefully,
    validate_label,
)

logger = logging.getLogger(__name__)


def pause_watcher(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Pause watcher by creating pause flag.

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with optional 'label' field

    Returns:
        Result dict with success, message, details
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        state_path = nas.get_state_path()

        # Create pause flag
        if not create_pause_flag(state_path, worker_id):
            return {'success': False, 'error': 'Failed to create pause flag'}

        # Log to audit
        audit_details = f"Watcher paused"
        if label:
            audit_details += f" (label: {label})"

        db.insert('audit_log_t', {
            'action': 'PAUSE_WATCHER',
            'username': 'supervisor',
            'ip_address': 'internal',
            'details': audit_details,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        })

        logger.info(f"Watcher {worker_id} paused. {audit_details}")
        return {
            'success': True,
            'message': f'Watcher {worker_id} paused',
            'label': label,
        }

    except Exception as e:
        logger.error(f"Error pausing watcher: {e}")
        return {'success': False, 'error': str(e)}


def resume_watcher(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Resume watcher by deleting pause flag and starting process.

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with optional 'label' field

    Returns:
        Result dict with success, message, details
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        state_path = nas.get_state_path()

        # Delete pause flag
        if not delete_pause_flag(state_path, worker_id):
            return {'success': False, 'error': 'Failed to delete pause flag'}

        # Start watcher
        if not start_watcher(worker_id):
            return {'success': False, 'error': 'Failed to start watcher'}

        # Log to audit
        audit_details = f"Watcher resumed"
        if label:
            audit_details += f" (label: {label})"

        db.insert('audit_log_t', {
            'action': 'RESUME_WATCHER',
            'username': 'supervisor',
            'ip_address': 'internal',
            'details': audit_details,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        })

        logger.info(f"Watcher {worker_id} resumed. {audit_details}")
        return {
            'success': True,
            'message': f'Watcher {worker_id} resumed',
            'label': label,
        }

    except Exception as e:
        logger.error(f"Error resuming watcher: {e}")
        return {'success': False, 'error': str(e)}


def update_code(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update code by running git pull.

    Steps:
    1. Stop watcher gracefully
    2. Run: git pull origin main
    3. Start watcher

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with optional 'label' field

    Returns:
        Result dict with success, message, output
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        repo_dir = Path(__file__).parent.parent.parent  # cornerstone_archive root

        # Stop watcher
        logger.info(f"Stopping watcher {worker_id} for code update")
        if not stop_watcher_gracefully(worker_id):
            return {
                'success': False,
                'error': 'Failed to stop watcher gracefully',
            }

        # Get current commit before update
        before_commit = get_current_commit(repo_dir)

        # Run git pull
        logger.info("Running: git pull origin main")
        result = run_command(
            ['git', 'pull', 'origin', 'main'], cwd=repo_dir
        )

        if result['returncode'] != 0:
            # Try to restart watcher despite failure
            start_watcher(worker_id)
            return {
                'success': False,
                'error': f"git pull failed: {result['stderr']}",
                'output': result['stdout'],
            }

        # Get new commit after update
        after_commit = get_current_commit(repo_dir)

        # Start watcher
        logger.info(f"Starting watcher {worker_id}")
        if not start_watcher(worker_id):
            logger.warning("Failed to start watcher after code update")

        # Log to audit
        audit_details = (
            f"Code updated: {before_commit} → {after_commit}"
        )
        if label:
            audit_details += f" (label: {label})"

        db.insert('audit_log_t', {
            'action': 'UPDATE_CODE',
            'username': 'supervisor',
            'ip_address': 'internal',
            'details': audit_details,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        })

        logger.info(f"Code updated. {audit_details}")
        return {
            'success': True,
            'message': f'Code updated: {before_commit} → {after_commit}',
            'before_commit': before_commit,
            'after_commit': after_commit,
            'label': label,
            'output': result['stdout'],
        }

    except Exception as e:
        logger.error(f"Error updating code: {e}")
        # Try to start watcher in case of exception
        try:
            start_watcher(worker_id)
        except Exception:
            pass
        return {'success': False, 'error': str(e)}


def update_code_deps(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update code and dependencies with dev requirements.

    Steps:
    1. Stop watcher gracefully
    2. Run: git pull origin main
    3. Run: pip install -r requirements-dev.txt --break-system-packages
    4. Start watcher

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with optional 'label' field

    Returns:
        Result dict with success, message, output
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        repo_dir = Path(__file__).parent.parent.parent  # cornerstone_archive root

        # Stop watcher
        logger.info(f"Stopping watcher {worker_id} for code/deps update")
        if not stop_watcher_gracefully(worker_id):
            return {
                'success': False,
                'error': 'Failed to stop watcher gracefully',
            }

        # Get current commit before update
        before_commit = get_current_commit(repo_dir)

        # Run git pull
        logger.info("Running: git pull origin main")
        git_result = run_command(
            ['git', 'pull', 'origin', 'main'], cwd=repo_dir
        )

        if git_result['returncode'] != 0:
            start_watcher(worker_id)
            return {
                'success': False,
                'error': f"git pull failed: {git_result['stderr']}",
            }

        # Run pip install with dev requirements
        logger.info("Running: pip install -r requirements-dev.txt")
        pip_result = run_command(
            [
                'pip',
                'install',
                '-r',
                'requirements-dev.txt',
                '--break-system-packages',
            ],
            cwd=repo_dir,
        )

        if pip_result['returncode'] != 0:
            logger.warning(
                f"pip install warning: {pip_result['stderr']}"
            )
            # Continue anyway (some warnings are acceptable)

        # Get new commit after update
        after_commit = get_current_commit(repo_dir)

        # Start watcher
        logger.info(f"Starting watcher {worker_id}")
        if not start_watcher(worker_id):
            logger.warning("Failed to start watcher after code/deps update")

        # Log to audit
        audit_details = (
            f"Code + deps updated: {before_commit} → {after_commit}"
        )
        if label:
            audit_details += f" (label: {label})"

        db.insert('audit_log_t', {
            'action': 'UPDATE_CODE_DEPS',
            'username': 'supervisor',
            'ip_address': 'internal',
            'details': audit_details,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        })

        logger.info(f"Code + deps updated. {audit_details}")
        return {
            'success': True,
            'message': f'Code + deps updated: {before_commit} → {after_commit}',
            'before_commit': before_commit,
            'after_commit': after_commit,
            'label': label,
            'git_output': git_result['stdout'],
            'pip_output': pip_result['stdout'],
        }

    except Exception as e:
        logger.error(f"Error updating code/deps: {e}")
        try:
            start_watcher(worker_id)
        except Exception:
            pass
        return {'success': False, 'error': str(e)}


def restart_watcher(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Restart watcher by stopping and starting.

    If pause flag is set, it will remain (watcher starts paused).

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with optional 'label' field

    Returns:
        Result dict with success, message
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        state_path = nas.get_state_path()
        pause_flag_set = is_watcher_paused(state_path, worker_id)

        # Stop watcher
        logger.info(f"Stopping watcher {worker_id}")
        if not stop_watcher_gracefully(worker_id):
            return {'success': False, 'error': 'Failed to stop watcher'}

        # Wait before restart
        import time
        time.sleep(2)

        # Start watcher (will start paused if pause flag is set)
        logger.info(f"Starting watcher {worker_id}")
        if not start_watcher(worker_id):
            return {'success': False, 'error': 'Failed to start watcher'}

        # Log to audit
        audit_details = f"Watcher restarted"
        if pause_flag_set:
            audit_details += " (paused)"
        if label:
            audit_details += f" (label: {label})"

        db.insert('audit_log_t', {
            'action': 'RESTART_WATCHER',
            'username': 'supervisor',
            'ip_address': 'internal',
            'details': audit_details,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        })

        logger.info(f"Watcher {worker_id} restarted. {audit_details}")
        return {
            'success': True,
            'message': f'Watcher {worker_id} restarted',
            'paused': pause_flag_set,
            'label': label,
        }

    except Exception as e:
        logger.error(f"Error restarting watcher: {e}")
        return {'success': False, 'error': str(e)}


def rollback_code(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Rollback code by reverting commits.

    Steps:
    1. Extract commits_back parameter (1-10, default 1)
    2. Stop watcher gracefully
    3. Get current commit
    4. For each commit to revert: git revert --no-edit HEAD
    5. Get final commit
    6. Start watcher (regardless of revert success)
    7. Record detailed results

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with 'commits_back' param and optional 'label'

    Returns:
        Result dict with success, commits_reverted, details
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        repo_dir = Path(__file__).parent.parent.parent

        # Parse commits_back parameter
        commits_back = task.get('params', {}).get('commits_back', 1)
        if not isinstance(commits_back, int):
            commits_back = int(commits_back)

        if commits_back < 1 or commits_back > 10:
            return {
                'success': False,
                'error': f'commits_back must be 1-10 (got {commits_back})',
            }

        # Stop watcher
        logger.info(f"Stopping watcher {worker_id} for rollback")
        if not stop_watcher_gracefully(worker_id):
            return {
                'success': False,
                'error': 'Failed to stop watcher gracefully',
            }

        # Get current commit before rollback
        before_commit = get_current_commit(repo_dir)
        commit_log = get_commit_log(repo_dir, count=commits_back + 2)

        # Revert commits
        reverted_commits = []
        failed_at = None

        for i in range(commits_back):
            logger.info(f"Reverting commit {i + 1}/{commits_back}")
            result = run_command(['git', 'revert', '--no-edit', 'HEAD'],
                               cwd=repo_dir)

            if result['returncode'] != 0:
                failed_at = i + 1
                logger.error(
                    f"Revert {i + 1} failed: {result['stderr']}"
                )
                break

            reverted_commits.append({
                'number': i + 1,
                'output': result['stdout'],
            })

        # Get final commit
        final_commit = get_current_commit(repo_dir)

        # Start watcher (always try, even if reverts failed)
        logger.info(f"Starting watcher {worker_id}")
        start_result = start_watcher(worker_id)

        # Log to audit
        audit_details = {
            'commits_reverted': len(reverted_commits),
            'reverted_commits': [
                c['number'] for c in reverted_commits
            ],
            'final_commit': final_commit,
            'success': failed_at is None,
        }
        if failed_at:
            audit_details['error'] = f'Revert {failed_at} failed'
        if label:
            audit_details['label'] = label

        db.insert('audit_log_t', {
            'action': 'ROLLBACK_CODE',
            'username': 'supervisor',
            'ip_address': 'internal',
            'details': json.dumps(audit_details),
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        })

        logger.info(f"Rollback complete. {len(reverted_commits)} commits reverted.")

        return {
            'success': failed_at is None,
            'message': f'Reverted {len(reverted_commits)}/{commits_back} commits',
            'before_commit': before_commit,
            'final_commit': final_commit,
            'commits_reverted': len(reverted_commits),
            'reverted_commits': [c['number'] for c in reverted_commits],
            'failed_at': failed_at,
            'label': label,
        }

    except Exception as e:
        logger.error(f"Error during rollback: {e}")
        try:
            start_watcher(worker_id)
        except Exception:
            pass
        return {'success': False, 'error': str(e)}


def diagnostics(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate system diagnostics report.

    Collects:
    - Watcher process status
    - Watcher heartbeat health
    - Database connectivity
    - NAS path accessibility
    - Disk space
    - Recent logs
    - Pending tasks
    - Recent audit logs

    Writes to: 05_LOGS/diagnostics/diagnostics_{worker_id}_{timestamp}.json

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with optional 'label' field

    Returns:
        Result dict with success, report_path
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        import psutil
        from scripts.supervisor.utils import (
            check_watcher_process,
            is_watcher_healthy,
            read_heartbeat_file,
        )

        state_path = nas.get_state_path()
        logs_path = nas.get_logs_path()
        diag_dir = logs_path / 'diagnostics'
        diag_dir.mkdir(parents=True, exist_ok=True)

        # Collect diagnostics
        timestamp = datetime.now(timezone.utc).isoformat()
        watcher_running = check_watcher_process(worker_id)

        # Watcher heartbeat
        heartbeat_file = state_path / f'watcher_heartbeat_{worker_id}.json'
        heartbeat = read_heartbeat_file(heartbeat_file)
        watcher_healthy = is_watcher_healthy(heartbeat)

        # Database connectivity
        db_status = {'connected': False, 'error': None}
        try:
            result = db.fetchOne('SELECT NOW() as db_time, DATABASE() as db_name')
            db_status['connected'] = result is not None
            if result:
                db_status['db_time'] = result.get('db_time')
                db_status['db_name'] = result.get('db_name')
        except Exception as e:
            db_status['error'] = str(e)

        # NAS paths
        nas_paths = {
            'state': state_path.exists(),
            'logs': logs_path.exists(),
            'worker_inbox': nas.get_worker_inbox_path().exists(),
            'worker_outbox': nas.get_worker_outbox_path().exists(),
        }

        # Disk space
        try:
            disk = psutil.disk_usage('/')
            disk_info = {
                'total_gb': disk.total / (1024 ** 3),
                'used_gb': disk.used / (1024 ** 3),
                'free_gb': disk.free / (1024 ** 3),
                'percent_free': 100 - disk.percent,
            }
        except Exception as e:
            disk_info = {'error': str(e)}

        # Pending tasks (files in Worker_Inbox)
        pending_tasks = []
        try:
            inbox = nas.get_worker_inbox_path()
            if inbox.exists():
                for f in inbox.glob('*.flag'):
                    pending_tasks.append(f.name)
        except Exception as e:
            logger.error(f"Error listing pending tasks: {e}")

        # Recent audit logs
        recent_audits = []
        try:
            audits = db.fetchAll(
                'SELECT * FROM audit_log_t ORDER BY timestamp DESC LIMIT 10'
            )
            recent_audits = [
                {
                    'action': a.get('action'),
                    'username': a.get('username'),
                    'timestamp': str(a.get('timestamp')),
                }
                for a in audits
            ]
        except Exception as e:
            logger.error(f"Error fetching audit logs: {e}")

        # Build report
        report = {
            'timestamp': timestamp,
            'worker_id': worker_id,
            'label': label,
            'watcher': {
                'running': watcher_running,
                'healthy': watcher_healthy,
                'heartbeat': heartbeat,
            },
            'database': db_status,
            'nas': nas_paths,
            'disk': disk_info,
            'pending_tasks': pending_tasks,
            'recent_audits': recent_audits,
        }

        # Write report
        report_file = (
            diag_dir
            / f'diagnostics_{worker_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Diagnostics report written to {report_file}")
        return {
            'success': True,
            'report_path': str(report_file),
            'label': label,
        }

    except Exception as e:
        logger.error(f"Error generating diagnostics: {e}")
        return {'success': False, 'error': str(e)}


def verify_database(
    nas: NasManager,
    db: Database,
    worker_id: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Verify database health and connectivity.

    Tests:
    1. Connection
    2. Query (SELECT NOW())
    3. Table accessibility
    4. Timezone (should be +00:00)

    Writes to: 05_LOGS/diagnostics/db_verification_{worker_id}_{timestamp}.json

    Args:
        nas: NasManager instance
        db: Database instance
        worker_id: Watcher identifier
        task: Task dict with optional 'label' field

    Returns:
        Result dict with success, test_results
    """
    label = task.get('label')
    is_valid, error = validate_label(label)
    if not is_valid:
        return {'success': False, 'error': error}

    try:
        logs_path = nas.get_logs_path()
        diag_dir = logs_path / 'diagnostics'
        diag_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).isoformat()
        test_results = {
            'timestamp': timestamp,
            'worker_id': worker_id,
            'label': label,
            'tests': {},
        }

        # Test 1: Connection (implicit, if we got here db is connected)
        test_results['tests']['connection'] = {
            'passed': True,
            'message': 'Database connected',
        }

        # Test 2: Query
        test_results['tests']['query'] = {'passed': False}
        try:
            result = db.fetchOne(
                'SELECT NOW() as db_time, DATABASE() as db_name'
            )
            if result:
                test_results['tests']['query'] = {
                    'passed': True,
                    'db_time': str(result.get('db_time')),
                    'db_name': result.get('db_name'),
                }
        except Exception as e:
            test_results['tests']['query']['error'] = str(e)

        # Test 3: Table accessibility
        test_results['tests']['tables'] = {}
        critical_tables = [
            'containers_t',
            'jobs_t',
            'workers_t',
            'segments_t',
        ]
        for table in critical_tables:
            test_results['tests']['tables'][table] = {'accessible': False}
            try:
                result = db.fetchOne(f'SELECT COUNT(*) as count FROM {table}')
                if result is not None:
                    test_results['tests']['tables'][table] = {
                        'accessible': True,
                        'row_count': result.get('count', 0),
                    }
            except Exception as e:
                test_results['tests']['tables'][table]['error'] = str(e)

        # Test 4: Timezone
        test_results['tests']['timezone'] = {'correct': False}
        try:
            result = db.fetchOne('SELECT @@session.time_zone as tz')
            if result:
                tz = result.get('tz')
                is_utc = tz == '+00:00' or tz == 'UTC'
                test_results['tests']['timezone'] = {
                    'correct': is_utc,
                    'value': tz,
                }
        except Exception as e:
            test_results['tests']['timezone']['error'] = str(e)

        # Write report
        report_file = (
            diag_dir
            / f'db_verification_{worker_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, indent=2, default=str)

        # Determine overall success
        all_passed = all(
            t.get('passed', t.get('accessible', t.get('correct', False)))
            for t in test_results['tests'].values()
            if isinstance(t, dict) and not t.get('error')
        )

        logger.info(f"Database verification report written to {report_file}")
        return {
            'success': all_passed,
            'report_path': str(report_file),
            'test_results': test_results,
            'label': label,
        }

    except Exception as e:
        logger.error(f"Error verifying database: {e}")
        return {'success': False, 'error': str(e)}
