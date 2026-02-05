"""Heartbeat recording for supervisor."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from scripts.common.spec_db import Database
from scripts.common.spec_nas import NasManager

logger = logging.getLogger(__name__)


def write_supervisor_heartbeat_file(
    nas: NasManager,
    worker_id: str,
    success: bool,
    error: Optional[str] = None,
    actions_taken: Optional[List[str]] = None,
) -> Path:
    """
    Write atomic heartbeat JSON to 00_STATE/.

    File: 00_STATE/supervisor_heartbeat_{worker_id}.json

    Uses tmp-then-replace for atomicity (no partial reads).

    Args:
        nas: NasManager instance
        worker_id: Watcher identifier
        success: Whether supervisor run was successful
        error: Error message if failed
        actions_taken: List of actions executed

    Returns:
        Path to heartbeat file
    """
    try:
        state_path = nas.get_state_path()
        state_path.mkdir(parents=True, exist_ok=True)

        heartbeat = {
            'supervisor_id': f'supervisor_{worker_id}',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'worker_id': worker_id,
            'success': success,
            'error': error,
            'actions': actions_taken or [],
        }

        target = state_path / f'supervisor_heartbeat_{worker_id}.json'
        tmp_path = target.with_suffix('.tmp')

        # Write to tmp file
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(heartbeat, f, indent=2)

        # Atomic replace
        tmp_path.replace(target)

        logger.info(f"Supervisor heartbeat written to {target}")
        return target

    except Exception as e:
        logger.error(f"Error writing supervisor heartbeat file: {e}")
        raise


def report_supervisor_heartbeat_to_database(
    db: Database,
    worker_id: str,
    success: bool,
    error: Optional[str] = None,
    actions_taken: Optional[List[str]] = None,
    watcher_state: str = 'unknown',
) -> None:
    """
    Record supervisor check results in workers_t table.

    Inserts or updates row with heartbeat info.

    Args:
        db: Database instance
        worker_id: Watcher identifier
        success: Whether supervisor run was successful
        error: Error message if failed
        actions_taken: List of actions executed
        watcher_state: Watcher status (running, stopped, paused, etc.)

    Returns:
        None
    """
    try:
        actions_str = ', '.join(actions_taken) if actions_taken else 'none'

        if success:
            status_summary = f"Supervisor OK - {watcher_state}. Actions: {actions_str}"
        else:
            status_summary = (
                f"Supervisor ERROR - {error}. State: {watcher_state}"
            )

        # Use INSERT ... ON DUPLICATE KEY UPDATE
        sql = """
            INSERT INTO workers_t (worker_id, last_heartbeat_at, status_summary)
            VALUES (%s, NOW(), %s)
            ON DUPLICATE KEY UPDATE
                last_heartbeat_at = NOW(),
                status_summary = VALUES(status_summary)
        """

        db.execute(sql, (f'supervisor_{worker_id}', status_summary))
        logger.debug(f"Supervisor heartbeat reported to database for {worker_id}")

    except Exception as e:
        logger.error(f"Error reporting supervisor heartbeat to database: {e}")
        # Don't raise - heartbeat failure shouldn't crash supervisor


def read_watcher_heartbeat(
    nas: NasManager, worker_id: str
) -> Optional[dict]:
    """
    Read watcher's latest heartbeat file.

    Path: 00_STATE/watcher_heartbeat_{worker_id}.json

    Args:
        nas: NasManager instance
        worker_id: Watcher identifier

    Returns:
        Parsed dict, or None if file missing/invalid
    """
    try:
        state_path = nas.get_state_path()
        heartbeat_file = state_path / f'watcher_heartbeat_{worker_id}.json'

        if not heartbeat_file.exists():
            logger.debug(f"Watcher heartbeat file not found: {heartbeat_file}")
            return None

        with open(heartbeat_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in watcher heartbeat file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading watcher heartbeat file: {e}")
        return None
