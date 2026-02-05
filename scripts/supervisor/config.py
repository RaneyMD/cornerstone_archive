"""Configuration loading for supervisor."""

import logging
from typing import Any, Dict, Tuple

from scripts.common.spec_config import ConfigError, load_config

logger = logging.getLogger(__name__)


def load_supervisor_config(config_path: str = "config.dev.yaml") -> Dict[str, Any]:
    """
    Load supervisor config from YAML.

    Uses scripts.common.spec_config.load_config() with supervisor validation.

    Args:
        config_path: Path to config file (default: config.dev.yaml)

    Returns:
        Config dict

    Raises:
        ConfigError: If config is invalid
    """
    try:
        config = load_config(config_path)
        logger.info(f"Loaded config from {config_path}")
        return config
    except ConfigError as e:
        logger.error(f"Config error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading config: {e}")
        raise ConfigError(f"Failed to load config: {e}")


def validate_supervisor_environment(
    nas_state_path, worker_id: str
) -> Tuple[bool, list]:
    """
    Validate supervisor can access all needed resources.

    Checks:
    - NAS state path accessible
    - Worker_Inbox exists
    - Worker_Outbox exists

    Args:
        nas_state_path: Path to NAS 00_STATE directory
        worker_id: Watcher identifier

    Returns:
        Tuple (valid: bool, issues: List[str])
    """
    issues = []

    # Check NAS state path
    if not nas_state_path.exists():
        issues.append(f"NAS state path not accessible: {nas_state_path}")
    else:
        logger.info(f"NAS state path accessible: {nas_state_path}")

    # Check Worker_Inbox
    try:
        from scripts.common.spec_nas import NasManager
        nas = NasManager(str(nas_state_path.parent.parent.parent))
        inbox = nas.get_worker_inbox_path()
        if not inbox.exists():
            inbox.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created Worker_Inbox: {inbox}")
    except Exception as e:
        issues.append(f"Error checking Worker_Inbox: {e}")

    # Check Worker_Outbox
    try:
        outbox = nas.get_worker_outbox_path()
        if not outbox.exists():
            outbox.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created Worker_Outbox: {outbox}")
    except Exception as e:
        issues.append(f"Error checking Worker_Outbox: {e}")

    return len(issues) == 0, issues
