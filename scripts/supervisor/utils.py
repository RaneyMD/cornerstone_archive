"""Utility functions for supervisor system."""

import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


def check_watcher_process(worker_id: str) -> bool:
    """
    Check if watcher process is currently running.

    Args:
        worker_id: Watcher identifier (e.g., 'OrionMX')

    Returns:
        True if watcher process is running, False otherwise
    """
    try:
        found_python_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info.get('name', '')
                cmdline = proc.info['cmdline'] or []

                # Log all Python processes for debugging
                if 'python' in name.lower():
                    found_python_procs.append({
                        'pid': proc.info['pid'],
                        'name': name,
                        'cmdline': ' '.join(cmdline[:3])  # First 3 args
                    })

                # Look for spec_watcher (file or module syntax) with this worker_id in cmdline
                cmdline_str = ' '.join(cmdline)
                # Match either:
                # - spec_watcher.py (file syntax)
                # - spec_watcher (module name or script name)
                # - scripts.watcher.spec_watcher (full module path)
                has_watcher = (
                    'spec_watcher.py' in cmdline_str
                    or 'spec_watcher' in cmdline_str
                    or 'scripts.watcher' in cmdline_str
                )
                has_worker_id = worker_id in cmdline_str

                if has_watcher and has_worker_id:
                    logger.debug(f"Found watcher process: PID {proc.info['pid']}, cmdline: {' '.join(cmdline[:5])}")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Log what we found for debugging
        if found_python_procs:
            logger.debug(f"Found {len(found_python_procs)} Python processes, but none matched watcher criteria for {worker_id}:")
            for p in found_python_procs:
                logger.debug(f"  PID {p['pid']}: {p['cmdline']}")
        else:
            logger.debug(f"No Python processes found when checking for {worker_id}")

        return False
    except Exception as e:
        logger.error(f"Error checking watcher process: {e}")
        return False


def is_watcher_healthy(heartbeat: Optional[Dict]) -> bool:
    """
    Determine if watcher heartbeat indicates healthy state.

    Checks:
    - Heartbeat exists
    - Heartbeat age < 5 minutes
    - Status field == 'running'

    Args:
        heartbeat: Parsed heartbeat dict

    Returns:
        True if watcher is healthy, False otherwise
    """
    if not heartbeat:
        return False

    try:
        # Check status field
        if heartbeat.get('status') != 'running':
            return False

        # Check heartbeat age
        timestamp_str = heartbeat.get('timestamp') or heartbeat.get('utc')
        if not timestamp_str:
            return False

        age = get_heartbeat_age_seconds(timestamp_str)
        if age is None or age > 300:  # 5 minutes
            return False

        return True
    except Exception as e:
        logger.error(f"Error checking watcher health: {e}")
        return False


def is_watcher_paused(nas_state_path: Path, worker_id: str) -> bool:
    """
    Check if pause flag exists.

    Args:
        nas_state_path: Path to NAS 00_STATE directory
        worker_id: Watcher identifier

    Returns:
        True if pause flag exists, False otherwise
    """
    try:
        pause_flag = nas_state_path / f"supervisor_pause_{worker_id}.flag"
        return pause_flag.exists()
    except Exception as e:
        logger.error(f"Error checking pause flag: {e}")
        return False


def read_heartbeat_file(path: Path) -> Optional[Dict]:
    """
    Read and parse heartbeat JSON file.

    Args:
        path: Path to heartbeat JSON file

    Returns:
        Parsed dict, or None if file missing/invalid
    """
    try:
        if not path.exists():
            return None

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in heartbeat file {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading heartbeat file {path}: {e}")
        return None


def stop_watcher_gracefully(
    worker_id: str, timeout_seconds: int = 30
) -> bool:
    """
    Stop watcher process gracefully.

    Sends SIGTERM, waits for graceful shutdown.
    If still running after timeout, sends SIGKILL.

    Args:
        worker_id: Watcher identifier
        timeout_seconds: Seconds to wait for graceful shutdown

    Returns:
        True if stopped, False if timeout/error
    """
    try:
        # Find watcher process
        target_proc = None
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline'] or []
                if (
                    'spec_watcher.py' in ' '.join(cmdline)
                    and worker_id in ' '.join(cmdline)
                ):
                    target_proc = proc
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not target_proc:
            logger.warning(f"Watcher process {worker_id} not found")
            return True  # Already not running

        pid = target_proc.pid
        logger.info(f"Sending SIGTERM to watcher {worker_id} (PID {pid})")

        # Send SIGTERM
        target_proc.terminate()

        # Wait for graceful shutdown
        start = time.time()
        while time.time() - start < timeout_seconds:
            try:
                if not target_proc.is_running():
                    logger.info(f"Watcher {worker_id} stopped gracefully")
                    return True
            except psutil.NoSuchProcess:
                logger.info(f"Watcher {worker_id} stopped gracefully")
                return True
            time.sleep(0.5)

        # Timeout - force kill
        logger.warning(f"Watcher {worker_id} did not stop, sending SIGKILL")
        target_proc.kill()
        time.sleep(1)

        try:
            if target_proc.is_running():
                logger.error(f"Failed to kill watcher {worker_id}")
                return False
        except psutil.NoSuchProcess:
            pass

        logger.info(f"Watcher {worker_id} killed forcefully")
        return True

    except Exception as e:
        logger.error(f"Error stopping watcher: {e}")
        return False


def start_watcher(
    worker_id: str = "OrionMX", config_path: str = "config.dev.yaml"
) -> bool:
    """
    Start watcher process with dev config.

    Runs in background via subprocess.Popen.

    Args:
        worker_id: Watcher identifier
        config_path: Path to config file

    Returns:
        True if process started, False if error
    """
    try:
        repo_dir = Path(__file__).parent.parent.parent  # cornerstone_archive root

        cmd = [
            "python",
            "-m",
            "scripts.watcher.spec_watcher",
            "--worker-id",
            worker_id,
            "--config",
            config_path,
        ]

        logger.info(f"Starting watcher {worker_id} with config {config_path}")
        proc = subprocess.Popen(
            cmd,
            cwd=repo_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        logger.info(f"Watcher {worker_id} started (PID {proc.pid})")
        return True

    except Exception as e:
        logger.error(f"Error starting watcher: {e}")
        return False


def get_heartbeat_age_seconds(timestamp_str: str) -> Optional[float]:
    """
    Get age of heartbeat in seconds.

    Handles ISO 8601 or MySQL datetime formats.

    Args:
        timestamp_str: Timestamp string (ISO 8601 or MySQL format)

    Returns:
        Age in seconds, or None if parsing fails
    """
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        age = (now - dt).total_seconds()
        return max(0, age)
    except Exception as e:
        logger.error(f"Error parsing timestamp {timestamp_str}: {e}")
        return None


def run_command(
    cmd: List[str], cwd: Optional[Path] = None, timeout_seconds: int = 30
) -> Dict:
    """
    Run shell command and capture output.

    Args:
        cmd: Command as list (e.g., ['git', 'pull'])
        cwd: Working directory
        timeout_seconds: Timeout in seconds

    Returns:
        Dict with 'returncode', 'stdout', 'stderr'
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': f'Command timed out after {timeout_seconds} seconds',
        }
    except Exception as e:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
        }


def validate_label(label: Optional[str]) -> Tuple[bool, str]:
    """
    Validate optional task label.

    Rules:
    - Max 100 characters (VARCHAR 100)
    - Alphanumeric, spaces, hyphens, underscores allowed
    - No special characters

    Args:
        label: Label string (or None)

    Returns:
        Tuple (is_valid: bool, error_msg: str or empty)
    """
    if label is None:
        return True, ""

    if not isinstance(label, str):
        return False, "Label must be a string"

    if len(label) > 100:
        return False, f"Label too long ({len(label)} > 100 characters)"

    # Check allowed characters: alphanumeric, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', label):
        return False, "Label contains invalid characters (only alphanumeric, spaces, hyphens, underscores allowed)"

    return True, ""


def create_pause_flag(nas_state_path: Path, worker_id: str) -> bool:
    """
    Create pause flag file.

    Args:
        nas_state_path: Path to NAS 00_STATE directory
        worker_id: Watcher identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        pause_flag = nas_state_path / f"supervisor_pause_{worker_id}.flag"
        pause_flag.touch()
        logger.info(f"Pause flag created: {pause_flag}")
        return True
    except Exception as e:
        logger.error(f"Error creating pause flag: {e}")
        return False


def delete_pause_flag(nas_state_path: Path, worker_id: str) -> bool:
    """
    Delete pause flag file.

    Args:
        nas_state_path: Path to NAS 00_STATE directory
        worker_id: Watcher identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        pause_flag = nas_state_path / f"supervisor_pause_{worker_id}.flag"
        if pause_flag.exists():
            pause_flag.unlink()
            logger.info(f"Pause flag deleted: {pause_flag}")
        return True
    except Exception as e:
        logger.error(f"Error deleting pause flag: {e}")
        return False


def get_current_commit(repo_dir: Path) -> Optional[str]:
    """
    Get current git commit (short SHA).

    Args:
        repo_dir: Path to git repository

    Returns:
        Short commit SHA, or None if error
    """
    result = run_command(['git', 'rev-parse', '--short', 'HEAD'], cwd=repo_dir)
    if result['returncode'] == 0:
        return result['stdout'].strip()
    return None


def get_commit_log(
    repo_dir: Path, count: int = 10
) -> Optional[List[str]]:
    """
    Get git commit log (short format).

    Args:
        repo_dir: Path to git repository
        count: Number of commits to retrieve

    Returns:
        List of commit lines, or None if error
    """
    result = run_command(
        ['git', 'log', '--oneline', f'-n{count}'], cwd=repo_dir
    )
    if result['returncode'] == 0:
        return result['stdout'].strip().split('\n')
    return None
