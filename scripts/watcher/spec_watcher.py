"""Main watcher orchestration loop for Cornerstone Archive.

Continuously scans for task flags, claims them atomically, executes handlers,
and records results. Handles graceful shutdown and database heartbeats.
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Any
from logging.handlers import RotatingFileHandler

from scripts.common.spec_config import load_config, ConfigError
from scripts.common.spec_nas import NasManager, NasError
from scripts.common.spec_db import Database, DatabaseError


logger = logging.getLogger(__name__)


class WatcherError(Exception):
    """Base exception for watcher errors."""

    pass


class TaskClaimError(WatcherError):
    """Exception raised when task cannot be claimed."""

    pass


class HandlerNotFoundError(WatcherError):
    """Exception raised when handler is not found."""

    pass


class TaskExecutionError(WatcherError):
    """Exception raised when task execution fails."""

    pass


class Watcher:
    """Main watcher orchestration system.

    Scans pending/ directory for task flags, claims them atomically,
    executes appropriate handlers, and records results.
    """

    def __init__(
        self,
        config: dict,
        nas_manager: NasManager,
        db: Database,
        worker_id: str = "OrionMX",
    ):
        """Initialize watcher.

        Args:
            config: Configuration dictionary from spec_config
            nas_manager: NasManager instance for path utilities
            db: Database instance for state management
            worker_id: Identifier for this worker (e.g., "OrionMX")
        """
        self.config = config
        self.nas = nas_manager
        self.db = db
        self.worker_id = worker_id
        self.running = True
        self.last_heartbeat = None

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)

        logger.info(f"Watcher initialized (worker_id={worker_id})")

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def run(self, dry_run: bool = False) -> int:
        """Run the main watcher loop.

        Args:
            dry_run: If True, scan tasks but don't execute them.

        Returns:
            Exit code (0 for clean shutdown, 1 for error)
        """
        logger.info("Watcher started")

        try:
            while self.running:
                try:
                    # Scan for pending tasks
                    tasks = self.scan_pending_tasks()
                    if tasks:
                        logger.debug(f"Found {len(tasks)} pending tasks")

                        # Process each task
                        for task in tasks:
                            if not self.running:
                                break

                            self._process_task(task, dry_run)

                    # Report heartbeat periodically
                    self._report_heartbeat_if_needed()

                    # Sleep before next scan
                    scan_interval = self.config.get("watcher", {}).get(
                        "scan_interval_seconds", 30
                    )
                    time.sleep(scan_interval)

                except Exception as e:
                    logger.error(f"Error in watcher loop: {e}", exc_info=True)
                    if not self.running:
                        break
                    time.sleep(5)  # Brief pause before retry

            logger.info("Watcher shutdown complete")
            return 0

        except Exception as e:
            logger.error(f"Fatal error in watcher: {e}", exc_info=True)
            return 1

    def _process_task(self, task: dict, dry_run: bool = False) -> None:
        """Process a single task.

        Args:
            task: Task dictionary with metadata
            dry_run: If True, don't actually execute
        """
        task_id = task.get("task_id", "unknown")

        try:
            logger.info(f"[TASK:{task_id}] Processing")

            if dry_run:
                logger.info(f"[TASK:{task_id}] DRY_RUN: Would execute {task.get('handler')}")
                return

            # Attempt to claim task
            if not self.claim_task(task_id):
                logger.debug(f"[TASK:{task_id}] Already claimed by another worker")
                return

            # Execute handler
            result = self.execute_handler(task)

            # Record success
            self.record_result(task, result, success=True)
            logger.info(f"[TASK:{task_id}] Completed successfully")

        except TaskExecutionError as e:
            logger.error(f"[TASK:{task_id}] Execution error: {e}")
            self.record_result(task, {"error": str(e)}, success=False)
        except Exception as e:
            logger.error(f"[TASK:{task_id}] Unexpected error: {e}", exc_info=True)
            self.record_result(task, {"error": str(e)}, success=False)

    def scan_pending_tasks(self) -> list:
        """Scan Worker_Inbox for incoming job flags.

        The Worker_Inbox is where job flags are placed for the watcher to discover.
        In the full system, the console writes jobs here via Console_Outbox.

        Returns:
            List of task dictionaries (empty if no pending tasks)
        """
        inbox_path = self.nas.get_worker_inbox_path()

        if not inbox_path.exists():
            return []

        tasks = []
        try:
            for flag_file in sorted(inbox_path.glob("*.flag")):
                try:
                    with open(flag_file, "r") as f:
                        task = json.load(f)
                        tasks.append(task)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to load task flag {flag_file.name}: {e}")

        except Exception as e:
            logger.error(f"Error scanning Worker_Inbox: {e}")

        return tasks

    def claim_task(self, task_id: str) -> bool:
        """Attempt to claim a task atomically.

        Moves task from Worker_Inbox to processing/ (temporary state during execution).
        This ensures only one worker processes each task.

        Args:
            task_id: Task ID to claim

        Returns:
            True if claimed successfully, False if already claimed

        Raises:
            TaskClaimError: If claim fails for other reasons
        """
        inbox_path = self.nas.get_worker_inbox_path()
        processing_path = self.nas.get_logs_path() / "processing"

        # Ensure processing directory exists
        processing_path.mkdir(parents=True, exist_ok=True)

        flag_file = inbox_path / f"{task_id}.flag"
        processing_file = processing_path / f"{task_id}.flag"

        try:
            # Atomic rename (cross-platform)
            flag_file.rename(processing_file)
            logger.debug(f"Claimed task from Worker_Inbox: {task_id}")
            return True
        except FileNotFoundError:
            # Task already claimed by another worker
            return False
        except Exception as e:
            raise TaskClaimError(f"Failed to claim task {task_id}: {e}") from e

    def execute_handler(self, task: dict) -> dict:
        """Execute appropriate handler for task.

        Args:
            task: Task dictionary with handler name and params

        Returns:
            Result dictionary from handler

        Raises:
            HandlerNotFoundError: If handler not found
            TaskExecutionError: If handler fails
        """
        handler_name = task.get("handler")
        task_id = task.get("task_id", "unknown")

        if not handler_name:
            raise TaskExecutionError("Task has no handler specified")

        # Get handler
        handler = get_handler(handler_name)
        if not handler:
            raise HandlerNotFoundError(f"Unknown handler: {handler_name}")

        try:
            logger.debug(f"[TASK:{task_id}] Executing handler: {handler_name}")
            result = handler(task, self.nas, self.db)
            logger.debug(f"[TASK:{task_id}] Handler result: {result}")
            return result
        except Exception as e:
            raise TaskExecutionError(f"Handler {handler_name} failed: {e}") from e

    def record_result(self, task: dict, result: dict, success: bool) -> None:
        """Record task result to Worker_Outbox.

        Writes results to the Worker_Outbox where the console can retrieve them.
        Success results are written as {task_id}.result.json
        Failure results are written as {task_id}.error.json

        Args:
            task: Task dictionary
            result: Result dictionary from handler
            success: Whether task succeeded
        """
        task_id = task.get("task_id", "unknown")
        processing_path = self.nas.get_logs_path() / "processing"
        outbox_path = self.nas.get_worker_outbox_path()

        # Ensure outbox directory exists
        outbox_path.mkdir(parents=True, exist_ok=True)

        try:
            # Remove processing flag file
            source_flag = processing_path / f"{task_id}.flag"
            if source_flag.exists():
                source_flag.unlink()

            # Write result to Worker_Outbox
            result_filename = f"{task_id}.result.json" if success else f"{task_id}.error.json"
            result_file = outbox_path / result_filename

            # Get UTC timestamp
            completed_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"

            result_data = {
                "task_id": task_id,
                "success": success,
                "completed_at": completed_at,
                "result": result,
            }
            with open(result_file, "w") as f:
                json.dump(result_data, f, indent=2)

            status = "success" if success else "failure"
            logger.debug(f"[TASK:{task_id}] Result ({status}) recorded to Worker_Outbox/")

        except Exception as e:
            logger.error(f"[TASK:{task_id}] Failed to record result: {e}")

    def _report_heartbeat_if_needed(self) -> None:
        """Report heartbeat to database if interval has passed."""
        heartbeat_interval = self.config.get("watcher", {}).get(
            "heartbeat_interval_seconds", 300
        )
        now = time.time()

        if (
            self.last_heartbeat is None
            or (now - self.last_heartbeat) >= heartbeat_interval
        ):
            try:
                self.report_heartbeat()
                self.last_heartbeat = now
            except Exception as e:
                logger.warning(f"Failed to report heartbeat: {e}")

    def report_heartbeat(self) -> None:
        """Report worker heartbeat to database.

        Updates or inserts row in workers_t table with UTC timestamp.
        The database connection is set to UTC, so NOW() returns UTC time.

        Raises:
            DatabaseError is caught and logged as warning
        """
        try:
            inbox_tasks = len(self.scan_pending_tasks())
            status_summary = f"Watcher running, {inbox_tasks} tasks in Worker_Inbox"

            # Use INSERT ... ON DUPLICATE KEY UPDATE to upsert
            # Note: Database connection is set to UTC, so NOW() returns UTC time
            sql = """
                INSERT INTO workers_t (worker_id, last_heartbeat_at, status_summary)
                VALUES (%s, NOW(), %s)
                ON DUPLICATE KEY UPDATE
                    last_heartbeat_at = NOW(),
                    status_summary = VALUES(status_summary)
            """
            self.db.execute(sql, (self.worker_id, status_summary))
            logger.debug(f"Heartbeat reported for {self.worker_id} (UTC)")

        except DatabaseError as e:
            logger.warning(f"Failed to report heartbeat to database: {e}")


def get_handler(handler_name: str) -> Optional[Callable]:
    """Get handler function by name.

    Args:
        handler_name: Name of handler (e.g., 'acquire_source')

    Returns:
        Handler function or None if not found
    """
    # Import handlers here to avoid circular imports
    try:
        if handler_name == "acquire_source":
            from scripts.stage1.acquire_source import acquire_source

            return acquire_source
        # Add more handlers as they're implemented
        # elif handler_name == "extract_pages":
        #     from scripts.stage2.extract_pages import extract_pages
        #     return extract_pages
    except ImportError:
        pass

    return None


def main(args: list = None) -> int:
    """Main entry point for watcher.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description="Cornerstone Archive watcher orchestration")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan tasks but don't execute handlers",
    )
    parser.add_argument(
        "--worker-id",
        default="OrionMX",
        help="Identifier for this worker (default: OrionMX)",
    )

    parsed = parser.parse_args(args)

    # Configure logging
    try:
        config = load_config(parsed.config)
        log_path = Path(config.get("logging", {}).get("path", "logs"))
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / "watcher.log"

        # Set up file and console logging
        log_format = "[%(asctime)s] [%(levelname)s] %(message)s"
        log_level = logging.INFO

        # File handler (rotating)
        fh = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=30
        )
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter(log_format))

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(log_level)
        ch.setFormatter(logging.Formatter(log_format))

        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(fh)
        root_logger.addHandler(ch)

    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    try:
        # Initialize components
        nas = NasManager(config)
        db = Database(config["database"])

        # Create and run watcher
        watcher = Watcher(config, nas, db, worker_id=parsed.worker_id)
        exit_code = watcher.run(dry_run=parsed.dry_run)

        db.close()
        return exit_code

    except (ConfigError, NasError, DatabaseError) as e:
        logger.error(f"Initialization error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
