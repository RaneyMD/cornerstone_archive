"""Main watcher orchestration loop for Cornerstone Archive.

Continuously scans for task flags, claims them atomically, executes handlers,
and records results. Handles graceful shutdown and database heartbeats.
"""

import argparse
import json
import logging
import os
import subprocess
import signal
import socket
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
MAX_PROMPT_BYTES = 100 * 1024
CLAUDE_ALLOWED_TOOLS = "Write,Edit,Bash"
CLAUDE_OUTPUT_FORMAT = "json"
CLAUDE_DEFAULT_TIMEOUT_SECONDS = 300
CLAUDE_VALID_MODELS = {"opus", "sonnet", "haiku"}


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


class PromptFileError(WatcherError):
    """Exception raised when prompt file loading fails."""

    pass


class ClaudeExecutionError(WatcherError):
    """Exception raised when Claude execution fails."""

    pass


class ClaudePromptRunner:
    """Utility for loading a prompt file and invoking Claude Code."""

    def __init__(
        self,
        prompt_path: Path,
        *,
        model: Optional[str] = None,
        dry_run: bool = False,
        timeout_seconds: int = CLAUDE_DEFAULT_TIMEOUT_SECONDS,
    ):
        self.prompt_path = prompt_path
        self.model = model
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.prompt_text = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load prompt file contents, enforcing size and readability."""
        try:
            if not self.prompt_path.exists():
                raise PromptFileError(f"Prompt file not found: {self.prompt_path}")
            if not self.prompt_path.is_file():
                raise PromptFileError(f"Prompt path is not a file: {self.prompt_path}")
            size_bytes = self.prompt_path.stat().st_size
        except OSError as e:
            raise PromptFileError(f"Unable to access prompt file: {e}") from e

        if size_bytes > MAX_PROMPT_BYTES:
            raise PromptFileError(
                f"Prompt file exceeds {MAX_PROMPT_BYTES} bytes: {self.prompt_path}"
            )

        try:
            return self.prompt_path.read_text(encoding="utf-8")
        except OSError as e:
            raise PromptFileError(f"Unable to read prompt file: {e}") from e

    def run(self) -> dict:
        """Invoke Claude Code with the prompt file contents."""
        command = [
            "claude",
            "-p",
            self.prompt_text,
            "--allowedTools",
            CLAUDE_ALLOWED_TOOLS,
            "--output-format",
            CLAUDE_OUTPUT_FORMAT,
        ]
        if self.model:
            command.extend(["--model", self.model])

        logger.info(
            "Claude invocation prepared (prompt_file=%s, bytes=%s, model=%s, dry_run=%s)",
            self.prompt_path,
            len(self.prompt_text.encode("utf-8")),
            self.model or "default",
            self.dry_run,
        )

        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "command": command,
            }

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise ClaudeExecutionError(
                f"Claude invocation timed out after {self.timeout_seconds} seconds"
            ) from e
        except OSError as e:
            raise ClaudeExecutionError(f"Failed to execute Claude: {e}") from e

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            raise ClaudeExecutionError(
                "Claude invocation failed with return code "
                f"{result.returncode}: {stderr or stdout}"
            )

        parsed_output: Optional[dict] = None
        if stdout:
            try:
                parsed_output = json.loads(stdout)
            except json.JSONDecodeError:
                parsed_output = self._parse_json_from_output(stdout)

        logger.info(
            "Claude invocation completed (stdout_bytes=%s, stderr_bytes=%s)",
            len(result.stdout),
            len(result.stderr),
        )

        return {
            "success": True,
            "dry_run": False,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "parsed": parsed_output,
        }

    def _parse_json_from_output(self, output: str) -> dict:
        """Attempt to extract JSON from stdout if leading text is present."""
        start = output.find("{")
        if start == -1:
            raise ClaudeExecutionError("Claude output was not valid JSON")
        for index in range(start, len(output)):
            if output[index] != "{":
                continue
            try:
                return json.loads(output[index:])
            except json.JSONDecodeError:
                continue
        raise ClaudeExecutionError("Claude output was not valid JSON")


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
        prompt_runner: Optional[ClaudePromptRunner] = None,
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
        self.lock_dir: Optional[Path] = None
        self.prompt_runner = prompt_runner

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)

        logger.info(f"Watcher initialized (worker_id={worker_id})")

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.release_lock()

    def run(self) -> int:
        """Run the main watcher event loop.

        Polls on a 1-second tick. Scans only when scan_interval has elapsed;
        reports heartbeat (DB upsert + file) only when heartbeat_interval has elapsed.

        Returns:
            Exit code (0 for clean shutdown, 1 for error)
        """
        logger.info("Watcher event loop starting")

        scan_interval = self.config.get("watcher", {}).get(
            "scan_interval_seconds", 30
        )
        heartbeat_interval = self.config.get("watcher", {}).get(
            "heartbeat_interval_seconds", 300
        )

        try:
            now = time.time()
            last_scan_time = now
            last_heartbeat_time = now

            # Unconditional initial heartbeat before the loop
            try:
                self.report_heartbeat()
                self.write_heartbeat_file()
                logger.info("Reported heartbeat to database and file")
            except Exception as e:
                logger.warning(f"Initial heartbeat failed: {e}")

            while self.running:
                time.sleep(1)
                if not self.running:
                    break

                now = time.time()

                # --- scan gate ---
                if (now - last_scan_time) >= scan_interval:
                    try:
                        tasks = self.scan_pending_tasks()
                        logger.info(
                            f"Scanned Worker_Inbox/, found {len(tasks)} pending tasks"
                        )
                        for task in tasks:
                            if not self.running:
                                break
                            self.process_task(task)
                        last_scan_time = now
                    except Exception as e:
                        logger.error(f"Error during scan/process: {e}", exc_info=True)

                # --- heartbeat gate ---
                if (now - last_heartbeat_time) >= heartbeat_interval:
                    try:
                        self.report_heartbeat()
                        self.write_heartbeat_file()
                        last_heartbeat_time = now
                        logger.info("Reported heartbeat to database and file")
                    except Exception as e:
                        logger.warning(f"Failed to report heartbeat: {e}")

            logger.info("Watcher shutdown complete")
            return 0

        except Exception as e:
            logger.error(f"Fatal error in watcher: {e}", exc_info=True)
            return 1

    def process_task(self, task: dict) -> None:
        """Process a single task.

        Args:
            task: Task dictionary with metadata
        """
        task_id = task.get("task_id", "unknown")

        try:
            logger.info(f"[TASK:{task_id}] Processing")

            # Attempt to claim task
            if not self.claim_task(task_id):
                logger.debug(f"[TASK:{task_id}] Already claimed by another worker")
                return

            # Execute handler
            result = self.execute_handler(task)

            prompt_result = self.run_prompt_if_configured(task)
            if prompt_result is not None:
                result = {**result, "prompt_execution": prompt_result}

            # Record success
            self.record_result(task, result, success=True)
            logger.info(f"[TASK:{task_id}] Completed successfully")

        except TaskExecutionError as e:
            logger.error(f"[TASK:{task_id}] Execution error: {e}")
            self.record_result(task, {"error": str(e)}, success=False)
        except Exception as e:
            logger.error(f"[TASK:{task_id}] Unexpected error: {e}", exc_info=True)
            self.record_result(task, {"error": str(e)}, success=False)

    def acquire_lock(self) -> Optional[Path]:
        """Acquire single-instance lock via atomic mkdir.

        Lock directory: 00_STATE/locks/watcher_{worker_id}.lock/
        mkdir() without exist_ok is atomic on all target filesystems —
        fails with FileExistsError if another instance holds it.

        Returns:
            Path to lock directory if acquired, None if already locked.
        """
        locks_dir = self.nas.get_state_path() / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)

        lock_dir = locks_dir / f"watcher_{self.worker_id}.lock"
        try:
            lock_dir.mkdir()  # atomic — raises FileExistsError if exists
            self.write_lock_owner(lock_dir)
            self.lock_dir = lock_dir
            logger.info(f"Lock acquired: {lock_dir}")
            return lock_dir
        except FileExistsError:
            logger.warning(f"Lock already held: {lock_dir}")
            return None

    def write_lock_owner(self, lock_dir: Path) -> None:
        """Write owner.json inside the lock directory.

        Args:
            lock_dir: Path to the lock directory (must already exist).
        """
        owner = {
            "watcher_id": self.worker_id,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "executable": sys.executable,
            "utc_locked_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        }
        owner_file = lock_dir / "owner.json"
        owner_file.write_text(json.dumps(owner, indent=2), encoding="utf-8")

    def release_lock(self) -> None:
        """Release the lock by removing owner.json then the lock directory.

        Safe to call when no lock is held (self.lock_dir is None).
        Idempotent: sets self.lock_dir = None in finally so repeated calls are no-ops.
        """
        if self.lock_dir is None:
            return
        try:
            owner_file = self.lock_dir / "owner.json"
            if owner_file.exists():
                owner_file.unlink()
            self.lock_dir.rmdir()
            logger.info(f"Lock released: {self.lock_dir}")
        except Exception as e:
            logger.warning(f"Failed to release lock {self.lock_dir}: {e}")
        finally:
            self.lock_dir = None

    def write_heartbeat_file(self) -> None:
        """Write heartbeat JSON atomically to 00_STATE/.

        Uses tmp-then-replace so a monitoring script never sees a partial file.
        Path.replace() (not .rename()) is used because .rename() raises on Windows
        if the target already exists.
        """
        state_path = self.nas.get_state_path()
        state_path.mkdir(parents=True, exist_ok=True)

        heartbeat_data = {
            "watcher_id": self.worker_id,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "status": "running",
            "utc": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
            "poll_seconds": self.config.get("watcher", {}).get(
                "scan_interval_seconds", 30
            ),
        }

        target = state_path / f"watcher_heartbeat_{self.worker_id}.json"
        tmp_path = target.with_suffix(".tmp")

        tmp_path.write_text(json.dumps(heartbeat_data, indent=2), encoding="utf-8")
        tmp_path.replace(target)  # atomic on same filesystem

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

    def run_prompt_if_configured(self, task: dict) -> Optional[dict]:
        """Run the configured Claude prompt after a successful handler."""
        if self.prompt_runner is None:
            return None

        task_id = task.get("task_id", "unknown")
        try:
            logger.info(f"[TASK:{task_id}] Running Claude prompt")
            return self.prompt_runner.run()
        except ClaudeExecutionError as e:
            logger.error(f"[TASK:{task_id}] Claude execution failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(
                f"[TASK:{task_id}] Unexpected Claude execution error: {e}",
                exc_info=True,
            )
            return {"success": False, "error": str(e)}

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
    parser.add_argument(
        "--prompt-file",
        help="Path to a markdown prompt file to run with Claude Code",
    )
    parser.add_argument(
        "--model",
        help="Model name to pass to Claude Code",
    )
    parser.add_argument(
        "--prompt-timeout",
        type=int,
        default=CLAUDE_DEFAULT_TIMEOUT_SECONDS,
        help="Timeout for Claude invocation in seconds",
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
        prompt_runner = None

        if parsed.prompt_file:
            if parsed.model and parsed.model not in CLAUDE_VALID_MODELS:
                logger.error(f"Invalid model: {parsed.model}")
                db.close()
                return 1
            prompt_path = Path(parsed.prompt_file).expanduser()
            if not prompt_path.is_absolute():
                prompt_path = (Path.cwd() / prompt_path).resolve()
            try:
                prompt_runner = ClaudePromptRunner(
                    prompt_path,
                    model=parsed.model,
                    dry_run=parsed.dry_run,
                    timeout_seconds=parsed.prompt_timeout,
                )
            except PromptFileError as e:
                logger.error(f"Prompt file error: {e}")
                db.close()
                return 1

        # Create watcher
        watcher = Watcher(
            config,
            nas,
            db,
            worker_id=parsed.worker_id,
            prompt_runner=prompt_runner,
        )

        # --- dry-run path: scan once, print, exit. No lock. ---
        if parsed.dry_run:
            tasks = watcher.scan_pending_tasks()
            logger.info(f"DRY_RUN: found {len(tasks)} pending tasks in Worker_Inbox/")
            for task in tasks:
                logger.info(
                    f"  [TASK:{task.get('task_id', 'unknown')}] "
                    f"handler={task.get('handler')}"
                )
            if prompt_runner is not None:
                logger.info(
                    "DRY_RUN: would invoke Claude prompt from %s after each handler",
                    prompt_runner.prompt_path,
                )
            db.close()
            return 0

        # --- normal mode: acquire lock, run loop, release in finally ---
        if watcher.acquire_lock() is None:
            logger.error(
                f"Another instance holds the lock for worker_id={parsed.worker_id}. Exiting."
            )
            db.close()
            return 1

        try:
            exit_code = watcher.run()
        finally:
            watcher.release_lock()
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
