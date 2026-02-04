"""Generate task flags for Internet Archive containers.

Creates task flag JSON files in the pending/ directory for the watcher
to discover and process.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from scripts.common.spec_config import load_config, ConfigError
from scripts.common.spec_nas import NasManager, NasError
from scripts.common.spec_db import Database, DatabaseError


logger = logging.getLogger(__name__)


class TaskGenerationError(Exception):
    """Exception raised during task generation."""

    pass


def generate_ia_tasks(
    ia_identifiers: List[str],
    nas: NasManager,
    db: Database,
) -> dict:
    """Generate task flags for list of IA identifiers.

    Args:
        ia_identifiers: List of IA identifiers
        nas: NasManager instance
        db: Database instance

    Returns:
        Dictionary with {"tasks_created": N, "tasks_queued": M, "errors": [...]}
    """
    results = {
        "tasks_created": 0,
        "tasks_queued": 0,
        "errors": [],
    }

    pending_path = nas.get_logs_path() / "flags" / "pending"
    pending_path.mkdir(parents=True, exist_ok=True)

    for ia_id in ia_identifiers:
        try:
            logger.debug(f"Processing IA identifier: {ia_id}")

            # Check if already processed
            existing = db.get_one(
                "SELECT container_id FROM containers_t WHERE source_identifier = %s",
                (ia_id,),
            )
            if existing:
                logger.debug(f"Container already exists for {ia_id}")
                continue

            # Allocate container ID
            container_id = _allocate_container_id(db)

            # Create task flag
            task_id = f"{datetime.now().strftime('%Y%m%d')}_{container_id:06d}_stage1"
            task_dict = {
                "task_id": task_id,
                "container_id": container_id,
                "stage": "stage1",
                "handler": "acquire_source",
                "params": {
                    "ia_identifier": ia_id,
                },
                "created_at": datetime.now().isoformat() + "Z",
                "max_retries": 3,
                "timeout_seconds": 3600,
            }

            # Write task flag to pending/
            flag_file = pending_path / f"{task_id}.flag"
            with open(flag_file, "w") as f:
                json.dump(task_dict, f, indent=2)

            logger.info(f"Created task: {task_id}")
            results["tasks_created"] += 1
            results["tasks_queued"] += 1

        except Exception as e:
            error_msg = f"Error processing {ia_id}: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

    return results


def _allocate_container_id(db: Database) -> int:
    """Allocate next available container ID.

    Args:
        db: Database instance

    Returns:
        Next container ID (numeric)

    Raises:
        DatabaseError: If database query fails
    """
    result = db.get_one("SELECT MAX(CAST(container_id AS UNSIGNED)) as max_id FROM containers_t")
    max_id = result.get("max_id", 0) if result else 0
    return int(max_id) + 1 if max_id else 1


def main(args: List[str] = None) -> int:
    """Main entry point for task generation.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description="Generate task flags for IA containers")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--file",
        help="File with one IA identifier per line",
    )
    parser.add_argument(
        "--id",
        help="Single IA identifier",
    )
    parser.add_argument(
        "--family",
        help="Family code (not yet implemented - would query IA for all items in family)",
    )

    parsed = parser.parse_args(args)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )

    try:
        # Load config and initialize components
        config = load_config(parsed.config)
        nas = NasManager(config)
        db = Database(config["database"])

        # Gather IA identifiers
        ia_identifiers = []

        if parsed.file:
            with open(parsed.file, "r") as f:
                ia_identifiers = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(ia_identifiers)} identifiers from file")

        elif parsed.id:
            ia_identifiers = [parsed.id]

        elif parsed.family:
            logger.error("--family not yet implemented")
            return 1

        else:
            parser.print_help()
            return 1

        if not ia_identifiers:
            logger.error("No identifiers specified")
            return 1

        # Generate tasks
        results = generate_ia_tasks(ia_identifiers, nas, db)

        # Print summary
        print()
        print(f"Created: {results['tasks_created']} tasks")
        print(f"Queued:  {results['tasks_queued']} tasks")
        if results["errors"]:
            print(f"Errors:  {len(results['errors'])}")
            for error in results["errors"]:
                print(f"  - {error}")
        print()

        db.close()

        return 0 if not results["errors"] else 1

    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except (NasError, DatabaseError) as e:
        logger.error(f"Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
