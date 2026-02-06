"""Control flow for processing supervisor flags."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.common.spec_db import Database
from scripts.common.spec_nas import NasManager
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

logger = logging.getLogger(__name__)

# Handler mapping
HANDLERS = {
    'pause_watcher': pause_watcher,
    'resume_watcher': resume_watcher,
    'update_code': update_code,
    'update_code_deps': update_code_deps,
    'restart_watcher': restart_watcher,
    'rollback_code': rollback_code,
    'diagnostics': diagnostics,
    'verify_db': verify_database,
}

# Handler priority (lower number = higher priority)
HANDLER_PRIORITY = {
    # Emergency/high-priority (none currently)
    # Code updates
    'rollback_code': 10,
    'update_code_deps': 11,
    'update_code': 12,
    # Operational
    'pause_watcher': 20,
    'resume_watcher': 21,
    'restart_watcher': 22,
    # Diagnostics
    'diagnostics': 30,
    'verify_db': 31,
}


def check_control_flags(
    inbox_path: Path,
    nas: NasManager,
    worker_id: str,
    db: Database,
) -> List[str]:
    """
    Scan Worker_Inbox for flag files and process in priority order.

    Flag processing order:
    1. Code updates (update_code, update_code_deps, rollback_code)
    2. Operational (pause, resume, restart_watcher)
    3. Diagnostics (diagnostics, verify_db)

    Returns list of actions taken (for logging/heartbeat).

    Args:
        inbox_path: Path to Worker_Inbox directory
        nas: NasManager instance
        worker_id: Watcher identifier
        db: Database instance

    Returns:
        List of action descriptions taken
    """
    actions_taken = []

    if not inbox_path.exists():
        logger.debug(f"Worker_Inbox not found: {inbox_path}")
        return actions_taken

    try:
        # Find all .flag files
        flag_files = list(inbox_path.glob('*.flag'))

        if not flag_files:
            logger.debug("No control flags found")
            return actions_taken

        logger.info(f"Found {len(flag_files)} control flag(s)")

        # Parse and sort by priority
        tasks = []
        for flag_file in flag_files:
            try:
                with open(flag_file, 'r', encoding='utf-8') as f:
                    task = json.load(f)

                handler = task.get('handler')
                if handler not in HANDLERS:
                    logger.warning(
                        f"Unknown handler '{handler}' in {flag_file.name}"
                    )
                    continue

                priority = HANDLER_PRIORITY.get(handler, 999)
                tasks.append({
                    'file': flag_file,
                    'task': task,
                    'handler': handler,
                    'priority': priority,
                })

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {flag_file.name}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error reading {flag_file.name}: {e}")
                continue

        # Sort by priority
        tasks.sort(key=lambda t: t['priority'])

        # Execute tasks
        for task_info in tasks:
            flag_file = task_info['file']
            task = task_info['task']
            handler_name = task_info['handler']

            try:
                logger.info(f"Processing {handler_name} from {flag_file.name}")

                # Get handler function
                handler_func = HANDLERS[handler_name]

                # Execute handler
                result = handler_func(nas, db, worker_id, task)

                # Write result file to Worker_Outbox for console to process
                task_id = task.get('task_id')
                job_id = task.get('job_id')
                log_path = str(nas.get_logs_path() / 'supervisor.log')
                write_result_file(
                    nas,
                    worker_id,
                    task_id=task_id,
                    job_id=job_id,
                    handler=handler_name,
                    success=result.get('success', False),
                    error=result.get('error'),
                    log_path=log_path,
                    result_details={
                        'message': result.get('message', ''),
                        'label': task.get('label'),
                    }
                )

                # Record action
                label = task.get('label', '')
                action_desc = f"{handler_name}"
                if label:
                    action_desc += f" ({label})"
                if not result.get('success'):
                    action_desc += f" - ERROR: {result.get('error', 'unknown')}"

                actions_taken.append(action_desc)

                logger.info(
                    f"Handler {handler_name} result: "
                    f"success={result.get('success')}, "
                    f"message={result.get('message', '')}"
                )

                # Delete flag file (success or failure)
                try:
                    flag_file.unlink()
                    logger.info(f"Deleted flag file: {flag_file.name}")
                except Exception as e:
                    logger.error(f"Failed to delete flag file {flag_file.name}: {e}")

            except Exception as e:
                logger.error(
                    f"Error executing handler {handler_name}: {e}"
                )
                actions_taken.append(
                    f"{handler_name} - EXCEPTION: {str(e)}"
                )

                # Write result file for exception case
                task_id = task.get('task_id')
                job_id = task.get('job_id')
                log_path = str(nas.get_logs_path() / 'supervisor.log')
                write_result_file(
                    nas,
                    worker_id,
                    task_id=task_id,
                    job_id=job_id,
                    handler=handler_name,
                    success=False,
                    error=str(e),
                    log_path=log_path,
                    result_details={
                        'exception': True,
                        'label': task.get('label'),
                    }
                )

                # Try to delete flag file even on error
                try:
                    flag_file.unlink()
                except Exception:
                    pass

        return actions_taken

    except Exception as e:
        logger.error(f"Error processing control flags: {e}")
        return actions_taken


def write_result_file(
    nas: NasManager,
    worker_id: str,
    task_id: Optional[str] = None,
    job_id: Optional[int] = None,
    handler: Optional[str] = None,
    success: bool = False,
    error: Optional[str] = None,
    log_path: Optional[str] = None,
    result_details: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Write result file to Worker_Outbox for console to process.

    Synology Cloud Sync monitors Worker_Outbox and syncs to console_inbox.

    Result file format: supervisor_result_{handler}_{task_id}_{timestamp}.json

    Args:
        nas: NasManager instance
        worker_id: Watcher identifier
        task_id: Task ID from control flag
        job_id: Job ID for direct correlation
        handler: Handler name (pause_watcher, etc.)
        success: Whether handler succeeded
        error: Error message if failed
        log_path: Path to supervisor log file
        result_details: Additional result data from handler

    Returns:
        True if result file written successfully, False otherwise
    """
    try:
        outbox_path = nas.get_worker_outbox_path()
        outbox_path.mkdir(parents=True, exist_ok=True)

        # Build result file name
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        safe_handler = handler or 'unknown'
        safe_task = task_id or 'notask'
        result_filename = f"supervisor_result_{safe_handler}_{safe_task}_{timestamp}.json"
        result_file = outbox_path / result_filename

        # Build result payload
        result_payload = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'supervisor_id': f'supervisor_{worker_id}',
            'worker_id': worker_id,
            'task_id': task_id,
            'job_id': job_id,
            'handler': handler,
            'success': success,
            'error': error,
            'log_path': log_path,
        }

        # Include additional details if provided
        if result_details:
            result_payload['details'] = result_details

        # Write result file atomically (tmp-then-replace)
        tmp_path = result_file.with_suffix('.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(result_payload, f, indent=2)

        tmp_path.replace(result_file)
        logger.info(
            f"Result file written: {result_filename} "
            f"(success={success}, handler={handler})"
        )
        return True

    except Exception as e:
        logger.error(f"Error writing result file: {e}")
        return False
