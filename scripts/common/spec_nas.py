"""NAS path utilities and validation for Cornerstone Archive.

Provides path construction following NAS_LAYOUT.md structure and validation
of NAS accessibility and permissions.
"""

import os
from pathlib import Path
from typing import Optional


class NasError(Exception):
    """Exception raised for NAS-related errors."""

    pass


class NasManager:
    """Manages NAS paths and validation.

    Constructs paths following the NAS directory structure and provides
    validation and creation utilities for working directories.
    """

    def __init__(self, config: dict):
        """Initialize NAS manager.

        Args:
            config: Configuration dictionary with 'nas' section containing 'root'.

        Raises:
            NasError: If config is invalid or NAS root not accessible.
        """
        if not isinstance(config, dict):
            raise NasError("Config must be a dictionary")

        nas_config = config.get("nas", {})
        if not nas_config.get("root"):
            raise NasError("Configuration must include nas.root")

        self.nas_root = Path(nas_config["root"])

        # Validate root exists and is accessible
        if not self.nas_root.exists():
            raise NasError(f"NAS root path does not exist: {self.nas_root}")

        if not os.access(self.nas_root, os.R_OK):
            raise NasError(f"NAS root path not readable: {self.nas_root}")

        self.config = config

    def get_raw_path(self, container_id: int) -> Path:
        """Get path to raw (intake) directory for a container.

        Args:
            container_id: Numeric container identifier.

        Returns:
            Path to 01_RAW/containers/{container_id}/ directory.
        """
        return self.nas_root / "01_RAW" / "containers" / str(container_id)

    def get_work_path(self, container_id: int) -> Path:
        """Get path to work (processing) directory for a container.

        Args:
            container_id: Numeric container identifier.

        Returns:
            Path to 02_WORK/containers/{container_id}/ directory.
        """
        return self.nas_root / "02_WORK" / "containers" / str(container_id)

    def get_logs_path(self) -> Path:
        """Get path to logs directory.

        Returns:
            Path to 05_LOGS/ directory.
        """
        return self.nas_root / "05_LOGS"

    def get_worker_inbox_path(self) -> Path:
        """Get path to worker inbox directory.

        The worker inbox is where job flags are received for processing.
        In the full system, the console writes to Console_Outbox and the
        watcher polls this inbox for incoming jobs.

        Returns:
            Path to 05_LOGS/Worker_Inbox/ directory.
        """
        return self.nas_root / "05_LOGS" / "Worker_Inbox"

    def get_worker_outbox_path(self) -> Path:
        """Get path to worker outbox directory.

        The worker outbox is where job results are written after execution.
        In the full system, the console polls Console_Inbox to retrieve
        results written here by the watcher.

        Returns:
            Path to 05_LOGS/Worker_Outbox/ directory.
        """
        return self.nas_root / "05_LOGS" / "Worker_Outbox"

    def get_reference_path(self) -> Path:
        """Get path to reference PDFs directory.

        Returns:
            Path to 03_REFERENCE/ directory.
        """
        return self.nas_root / "03_REFERENCE"

    def get_publish_path(self) -> Path:
        """Get path to publish payloads directory.

        Returns:
            Path to 04_PUBLISH/ directory.
        """
        return self.nas_root / "04_PUBLISH"

    def get_state_path(self) -> Path:
        """Get path to state snapshots directory.

        Returns:
            Path to 00_STATE/ directory.
        """
        return self.nas_root / "00_STATE"

    def is_accessible(self, path: Path) -> bool:
        """Check if a path is accessible (exists and readable).

        Args:
            path: Path to check.

        Returns:
            True if path exists and is readable, False otherwise.
        """
        try:
            path = Path(path)
            return path.exists() and os.access(path, os.R_OK)
        except (OSError, ValueError):
            return False

    def is_writable(self, path: Path) -> bool:
        """Check if a path is writable.

        Args:
            path: Path to check.

        Returns:
            True if path exists and is writable, False otherwise.
        """
        try:
            path = Path(path)
            return path.exists() and os.access(path, os.W_OK)
        except (OSError, ValueError):
            return False

    def create_work_dir(self, container_id: int) -> Path:
        """Create working directory for a container.

        Creates the directory if it doesn't exist. Parent directories are
        created as needed.

        Args:
            container_id: Numeric container identifier.

        Returns:
            Path to created work directory.

        Raises:
            NasError: If directory cannot be created due to permissions.
        """
        work_path = self.get_work_path(container_id)

        try:
            work_path.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise NasError(f"Permission denied creating work directory: {work_path}") from e
        except OSError as e:
            raise NasError(f"Failed to create work directory {work_path}: {e}") from e

        if not self.is_writable(work_path):
            raise NasError(f"Created directory is not writable: {work_path}")

        return work_path

    def verify_all_paths(self) -> dict:
        """Verify all standard NAS paths exist and are accessible.

        Returns:
            Dictionary with path names as keys and accessibility status as values.
            Example: {'01_RAW': True, '02_WORK': True, ...}
        """
        paths = {
            "00_STATE": self.get_state_path(),
            "01_RAW": self.nas_root / "01_RAW",
            "02_WORK": self.nas_root / "02_WORK",
            "03_REFERENCE": self.get_reference_path(),
            "04_PUBLISH": self.get_publish_path(),
            "05_LOGS": self.get_logs_path(),
        }

        results = {}
        for name, path in paths.items():
            results[name] = self.is_accessible(path)

        return results
