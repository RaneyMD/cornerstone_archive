"""Health check script for NAS accessibility and structure.

Verifies all required NAS directories exist, are accessible, and have
sufficient disk space. Can be run from command line for operational monitoring.
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from scripts.common.spec_config import load_config, ConfigError
from scripts.common.spec_nas import NasManager, NasError


logger = logging.getLogger(__name__)


class VerificationResult:
    """Encapsulates verification results for reporting."""

    def __init__(self):
        """Initialize result tracker."""
        self.ok_results: List[str] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def ok(self, message: str) -> None:
        """Record a successful check."""
        self.ok_results.append(message)

    def warn(self, message: str) -> None:
        """Record a warning."""
        self.warnings.append(message)

    def error(self, message: str) -> None:
        """Record an error."""
        self.errors.append(message)

    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def print_report(self, verbose: bool = False) -> None:
        """Print formatted report of results.

        Args:
            verbose: If True, include verbose output for all checks.
        """
        if self.ok_results and verbose:
            for msg in self.ok_results:
                print(f"[OK] {msg}")

        for msg in self.warnings:
            print(f"[WARN] {msg}")

        for msg in self.errors:
            print(f"[ERROR] {msg}")

        # Print summary
        summary_parts = []
        if self.ok_results:
            summary_parts.append(f"{len(self.ok_results)} OK")
        if self.warnings:
            summary_parts.append(f"{len(self.warnings)} WARN")
        if self.errors:
            summary_parts.append(f"{len(self.errors)} ERROR")

        print()
        if summary_parts:
            print(f"Summary: {', '.join(summary_parts)}")
        else:
            print("Summary: All checks passed")


def _format_size(bytes_val: float) -> str:
    """Format bytes as human-readable size string.

    Args:
        bytes_val: Number of bytes.

    Returns:
        Formatted string (e.g., "1.5 GB").
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"


def verify_path_exists(
    result: VerificationResult, name: str, path: Path
) -> bool:
    """Verify a path exists and is accessible.

    Args:
        result: Result tracker.
        name: Human-readable name for the path.
        path: Path to verify.

    Returns:
        True if path exists and is accessible, False otherwise.
    """
    if path.exists():
        result.ok(f"{name} directory exists: {path}")
        return True
    else:
        result.error(f"{name} directory not found: {path}")
        return False


def verify_path_writable(
    result: VerificationResult, name: str, path: Path
) -> bool:
    """Verify a path exists and is writable.

    Args:
        result: Result tracker.
        name: Human-readable name for the path.
        path: Path to verify.

    Returns:
        True if path is writable, False otherwise.
    """
    if not path.exists():
        result.error(f"{name} does not exist: {path}")
        return False

    import os

    if not os.access(path, os.W_OK):
        result.error(f"{name} is not writable: {path}")
        return False

    result.ok(f"{name} is writable: {path}")
    return True


def verify_disk_space(
    result: VerificationResult, path: Path, warn_percent: float = 10.0
) -> bool:
    """Verify sufficient disk space on volume containing path.

    Args:
        result: Result tracker.
        path: Path to check disk space for.
        warn_percent: Warn if free space is below this percentage.

    Returns:
        True if disk space is acceptable, False if critical.
    """
    try:
        stat = shutil.disk_usage(path)
        percent_free = (stat.free / stat.total) * 100

        if percent_free < 5.0:
            result.error(
                f"Critical: Disk space {percent_free:.1f}% free "
                f"({_format_size(stat.free)} of {_format_size(stat.total)})"
            )
            return False
        elif percent_free < warn_percent:
            result.warn(
                f"Disk space {percent_free:.1f}% free "
                f"({_format_size(stat.free)} of {_format_size(stat.total)}) - "
                f"consider cleanup"
            )
            return True
        else:
            result.ok(
                f"Disk space {percent_free:.1f}% free "
                f"({_format_size(stat.free)} of {_format_size(stat.total)})"
            )
            return True

    except OSError as e:
        result.error(f"Cannot determine disk space: {e}")
        return False


def verify_nas_paths(nas: NasManager, verbose: bool = False) -> VerificationResult:
    """Verify all NAS paths and structure.

    Args:
        nas: NasManager instance.
        verbose: If True, print verbose output.

    Returns:
        VerificationResult with all check results.
    """
    result = VerificationResult()

    # Verify standard directories
    standard_paths = {
        "00_STATE": nas.get_state_path(),
        "01_RAW": nas.nas_root / "01_RAW",
        "02_WORK": nas.nas_root / "02_WORK",
        "03_REFERENCE": nas.get_reference_path(),
        "04_PUBLISH": nas.get_publish_path(),
        "05_LOGS": nas.get_logs_path(),
    }

    for name, path in standard_paths.items():
        verify_path_exists(result, name, path)

    # Verify working directories are writable
    for name, path in standard_paths.items():
        if name in ["02_WORK", "05_LOGS"]:
            verify_path_writable(result, f"{name} (write access)", path)

    # Check disk space on NAS volume
    verify_disk_space(result, nas.nas_root)

    return result


def main(args: List[str] = None) -> int:
    """Main entry point for verification script.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for errors detected).
    """
    parser = argparse.ArgumentParser(
        description="Verify NAS accessibility and health for Cornerstone Archive"
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print verbose output"
    )

    parsed = parser.parse_args(args)

    # Configure logging
    log_level = logging.DEBUG if parsed.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(name)s] %(message)s",
    )

    try:
        # Load configuration
        config = load_config(parsed.config)
        logger.debug(f"Loaded config from {parsed.config}")

        # Initialize NAS manager
        nas = NasManager(config)
        logger.debug(f"NAS root: {nas.nas_root}")

        # Run verification
        result = verify_nas_paths(nas, verbose=parsed.verbose)

        # Print report
        result.print_report(verbose=parsed.verbose)

        # Return appropriate exit code
        return 1 if result.has_errors() else 0

    except ConfigError as e:
        print(f"[ERROR] Configuration error: {e}", file=sys.stderr)
        return 1
    except NasError as e:
        print(f"[ERROR] NAS error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        logger.debug(f"Exception: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
