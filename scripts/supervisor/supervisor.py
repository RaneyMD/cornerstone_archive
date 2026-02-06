"""Supervisor process for monitoring watcher health and processing control flags."""

import argparse
import logging
import logging.handlers
import signal
import sys
from pathlib import Path
from typing import Optional

from scripts.common.spec_config import ConfigError
from scripts.common.spec_db import Database, DatabaseError
from scripts.common.spec_nas import NasManager, NasError
from scripts.supervisor.config import (
    load_supervisor_config,
    validate_supervisor_environment,
)
from scripts.supervisor.control_flow import check_control_flags
from scripts.supervisor.heartbeat import (
    read_watcher_heartbeat,
    report_supervisor_heartbeat_to_database,
    write_supervisor_heartbeat_file,
)
from scripts.supervisor.utils import (
    check_watcher_process,
    is_watcher_healthy,
    is_watcher_paused,
    start_watcher,
)

logger = logging.getLogger(__name__)


class Supervisor:
    """Main supervisor orchestrator."""

    def __init__(self, config_path: str, worker_id: str = "OrionMX"):
        """
        Initialize supervisor with worker ID and config.

        Args:
            config_path: Path to config file
            worker_id: Watcher identifier

        Raises:
            ConfigError, NasError, DatabaseError
        """
        self.worker_id = worker_id
        self.config_path = config_path

        # Load config
        logger.info(f"Initializing supervisor for {worker_id}")
        self.config = load_supervisor_config(config_path)

        # Initialize NAS manager (pass full config)
        self.nas = NasManager(self.config)

        # Validate environment
        valid, issues = validate_supervisor_environment(self.nas, worker_id)
        if not valid:
            logger.warning(f"Environment validation issues: {issues}")

        # Initialize database (pass full config dict)
        db_config = self.config.get('database', {})
        self.db = Database(db_config)

        logger.info(
            f"Supervisor initialized for {worker_id} "
            f"(config: {config_path})"
        )

    def check_watcher_health(self) -> dict:
        """
        Check watcher health status.

        Returns:
            Dict with watcher status info
        """
        logger.info(f"Checking watcher health for {self.worker_id}")

        running = check_watcher_process(self.worker_id)
        heartbeat = read_watcher_heartbeat(self.nas, self.worker_id)
        healthy = is_watcher_healthy(heartbeat)

        status = {
            'running': running,
            'healthy': healthy,
            'heartbeat': heartbeat,
            'state': 'running' if running and healthy else (
                'stale' if running else 'stopped'
            ),
        }

        logger.info(
            f"Watcher health: running={running}, healthy={healthy}, "
            f"state={status['state']}"
        )

        return status

    def report_heartbeat_to_database(
        self, success: bool, error: Optional[str] = None,
        actions_taken: Optional[list] = None, watcher_state: str = 'unknown'
    ) -> None:
        """
        Report supervisor heartbeat to database.

        Args:
            success: Whether supervisor run was successful
            error: Error message if failed
            actions_taken: List of actions executed
            watcher_state: Watcher status string
        """
        try:
            report_supervisor_heartbeat_to_database(
                self.db,
                self.worker_id,
                success,
                error,
                actions_taken,
                watcher_state,
            )
        except Exception as e:
            logger.error(f"Failed to report heartbeat to database: {e}")

    def write_heartbeat_file(
        self, success: bool, error: Optional[str] = None,
        actions_taken: Optional[list] = None
    ) -> None:
        """
        Write supervisor heartbeat file.

        Args:
            success: Whether supervisor run was successful
            error: Error message if failed
            actions_taken: List of actions executed
        """
        try:
            write_supervisor_heartbeat_file(
                self.nas,
                self.worker_id,
                success,
                error,
                actions_taken,
            )
        except Exception as e:
            logger.error(f"Failed to write heartbeat file: {e}")

    def run_once(self) -> int:
        """
        Run supervisor once (single pass).

        Process:
        1. Check watcher health
        2. Auto-restart if stopped (unless paused)
        3. Process control flags
        4. Report heartbeat to database
        5. Write heartbeat file
        6. Exit

        Returns:
            Exit code (0 = success, 1 = error)
        """
        logger.info("=" * 60)
        logger.info(f"SUPERVISOR RUN START for {self.worker_id}")
        logger.info("=" * 60)

        error = None
        actions_taken = []

        try:
            # Check watcher health
            health = self.check_watcher_health()
            watcher_state = health['state']

            # Auto-restart if stopped (unless intentionally paused)
            if not health['running']:
                state_path = self.nas.get_state_path()
                if is_watcher_paused(state_path, self.worker_id):
                    logger.info(f"Watcher {self.worker_id} is paused, skipping auto-restart")
                else:
                    logger.warning(f"Watcher {self.worker_id} is stopped, auto-restarting...")
                    success = start_watcher(self.worker_id, self.config_path)
                    if success:
                        actions_taken.append('auto_restart_watcher')
                        watcher_state = 'restarting'
                        logger.info(f"Watcher {self.worker_id} restart initiated")
                    else:
                        logger.error(f"Failed to auto-restart watcher {self.worker_id}")
                        error = "Failed to auto-restart watcher"

            # Process control flags
            logger.info("Processing control flags...")
            inbox = self.nas.get_worker_inbox_path()
            actions = check_control_flags(
                inbox,
                self.nas,
                self.worker_id,
                self.db,
            )
            actions_taken.extend(actions)

            if actions:
                logger.info(f"Actions taken: {actions}")
            else:
                logger.info("No control flags processed")

            # Report heartbeat
            self.report_heartbeat_to_database(
                success=True,
                actions_taken=actions_taken,
                watcher_state=watcher_state,
            )

            # Write heartbeat file
            self.write_heartbeat_file(
                success=True,
                actions_taken=actions_taken,
            )

            logger.info("=" * 60)
            logger.info(f"SUPERVISOR RUN END (SUCCESS)")
            logger.info("=" * 60)

            return 0

        except (ConfigError, NasError, DatabaseError) as e:
            error = str(e)
            logger.error(f"Supervisor error: {error}")

            try:
                self.report_heartbeat_to_database(
                    success=False,
                    error=error,
                    actions_taken=actions_taken,
                )
                self.write_heartbeat_file(
                    success=False,
                    error=error,
                    actions_taken=actions_taken,
                )
            except Exception as e2:
                logger.error(f"Failed to report error: {e2}")

            logger.info("=" * 60)
            logger.info(f"SUPERVISOR RUN END (ERROR: {error})")
            logger.info("=" * 60)

            return 1

        except Exception as e:
            error = f"Unexpected error: {e}"
            logger.error(error, exc_info=True)

            try:
                self.report_heartbeat_to_database(
                    success=False,
                    error=error,
                    actions_taken=actions_taken,
                )
                self.write_heartbeat_file(
                    success=False,
                    error=error,
                    actions_taken=actions_taken,
                )
            except Exception as e2:
                logger.error(f"Failed to report error: {e2}")

            logger.info("=" * 60)
            logger.info(f"SUPERVISOR RUN END (EXCEPTION)")
            logger.info("=" * 60)

            return 1


def setup_logging(log_file: Path) -> None:
    """
    Set up logging to file and console with hourly rotation.

    Creates hourly log files in YYYY-MM-DD subdirectories:
    - Active: {log_dir}/supervisor.log
    - Archives: {log_dir}/YYYY-MM-DD/supervisor_HH.log

    Args:
        log_file: Path to log file (base name used for hourly logs)
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # File handler (rotating hourly, stores archives in date subfolders)
    # Using 'H' interval for hourly rotation, keeping 24 backups
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='H',  # Rotate at hour boundary
        interval=1,  # Every 1 hour
        backupCount=24,  # Keep 24 hours of logs
    )

    # Custom naming: archives go to YYYY-MM-DD subfolder as supervisor_HH.log
    def rotation_filename(default_name):
        # default_name format: supervisor.log.2026-02-06_23
        # Convert to: YYYY-MM-DD/supervisor_HH.log
        parts = default_name.split('.')
        if len(parts) >= 3:
            date_hour = parts[-1]  # e.g., "2026-02-06_23"
            date_part = date_hour.split('_')[0]  # e.g., "2026-02-06"
            hour_part = date_hour.split('_')[1] if '_' in date_hour else '00'  # e.g., "23"
            return str(log_file.parent / date_part / f"supervisor_{hour_part}.log")
        return default_name

    file_handler.namer = rotation_filename
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter(
        '[%(asctime)s] [SUPERVISOR] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger.info("Logging initialized (hourly rotation, archives in date subfolders)")


def main(args: Optional[list] = None) -> int:
    """
    Main entry point.

    Args:
        args: Command-line arguments (for testing)

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Supervisor process for watcher management"
    )
    parser.add_argument(
        '--worker-id',
        default='OrionMX',
        help='Worker identifier (default: OrionMX)',
    )
    parser.add_argument(
        '--config',
        default='config.dev.yaml',
        help='Path to config file (default: config.dev.yaml)',
    )

    parsed_args = parser.parse_args(args)

    # Load config and get NAS log path
    try:
        config = load_supervisor_config(parsed_args.config)
        nas = NasManager(config)
        log_dir = nas.get_logs_path()
        log_file = log_dir / 'supervisor.log'
    except (ConfigError, NasError) as e:
        print(f"Error loading config or NAS paths: {e}", file=sys.stderr)
        return 1

    # Set up logging to NAS
    try:
        setup_logging(log_file)
    except Exception as e:
        print(f"Error setting up logging: {e}", file=sys.stderr)
        return 1

    # Signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.warning(f"Received signal {signum}, exiting...")
        sys.exit(1)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run supervisor
    try:
        supervisor = Supervisor(
            config_path=parsed_args.config,
            worker_id=parsed_args.worker_id,
        )
        return supervisor.run_once()
    except Exception as e:
        logger.error(f"Failed to initialize supervisor: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
