"""Configuration loading and validation for Cornerstone Archive.

Loads YAML configuration with environment variable substitution and validates
required keys and values for both development and production environments.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ConfigError(Exception):
    """Exception raised for configuration errors."""

    pass


class Config(dict):
    """Dictionary-like configuration object with validation.

    Extends dict to provide dot-notation access and validation methods.
    """

    def __getattr__(self, name: str) -> Any:
        """Allow dot-notation access to config values."""
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Configuration has no attribute '{name}'")

    def validate(self) -> None:
        """Validate configuration has all required keys and valid values.

        Raises:
            ConfigError: If validation fails.
        """
        # Check required top-level keys
        required_top_level = {"database", "nas", "logging", "environment"}
        missing = required_top_level - set(self.keys())
        if missing:
            raise ConfigError(
                f"Missing required configuration sections: {', '.join(sorted(missing))}"
            )

        # Validate environment
        valid_environments = {"development", "production"}
        if self.get("environment") not in valid_environments:
            raise ConfigError(
                f"environment must be 'development' or 'production', "
                f"got '{self.get('environment')}'"
            )

        # Validate database section
        db_config = self.get("database", {})
        required_db_keys = {"host", "user", "database"}
        missing_db = required_db_keys - set(db_config.keys())
        if missing_db:
            raise ConfigError(
                f"Missing required database keys: {', '.join(sorted(missing_db))}"
            )

        # Password must be filled (not empty, not placeholder)
        password = db_config.get("password", "").strip()
        if not password or password == "${DB_PASSWORD}":
            raise ConfigError(
                "database.password must be set via environment variable "
                "(e.g., ${DB_PASSWORD})"
            )

        # Validate NAS section
        nas_config = self.get("nas", {})
        if "root" not in nas_config:
            raise ConfigError("Missing required nas.root configuration")

        # Validate logging section
        logging_config = self.get("logging", {})
        if "level" in logging_config:
            valid_levels = {"DEBUG", "INFO", "WARN", "ERROR"}
            if logging_config["level"] not in valid_levels:
                raise ConfigError(
                    f"logging.level must be one of {valid_levels}, "
                    f"got '{logging_config['level']}'"
                )

        # Validate watcher section if present
        if "watcher" in self:
            watcher_config = self.get("watcher", {})
            if "scan_interval_seconds" in watcher_config:
                interval = watcher_config["scan_interval_seconds"]
                if not isinstance(interval, (int, float)) or interval <= 0:
                    raise ConfigError(
                        f"watcher.scan_interval_seconds must be > 0, "
                        f"got {interval}"
                    )


def _substitute_env_variables(data: Any) -> Any:
    """Recursively substitute environment variables in configuration.

    Handles ${VAR_NAME} and ${VAR_NAME:default_value} syntax.

    Args:
        data: Configuration data (dict, list, or scalar).

    Returns:
        Configuration data with environment variables substituted.

    Raises:
        ConfigError: If required environment variable is not set.
    """
    if isinstance(data, dict):
        return {k: _substitute_env_variables(v) for k, v in data.items()}

    if isinstance(data, list):
        return [_substitute_env_variables(item) for item in data]

    if isinstance(data, str):
        # Match ${VAR_NAME} or ${VAR_NAME:default}
        pattern = r"\$\{([^:}]+)(?::([^}]*))?\}"

        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2)

            value = os.getenv(var_name)
            if value is None:
                if default_value is not None:
                    return default_value
                raise ConfigError(
                    f"Environment variable '{var_name}' not set and no default provided"
                )
            return value

        return re.sub(pattern, replace_var, data)

    return data


def load_config(config_path: Optional[str] = None) -> Config:
    """Load and validate configuration from YAML file.

    Substitutes environment variables (${VAR_NAME} syntax) and validates
    that all required keys are present and valid.

    Args:
        config_path: Path to YAML config file. Defaults to config/config.yaml
                     relative to the repository root.

    Returns:
        Config object (dict-like with validation).

    Raises:
        ConfigError: If file not found, YAML parsing fails, or validation fails.
        FileNotFoundError: If config file doesn't exist.
    """
    if config_path is None:
        # Default to config/config.yaml relative to repo root
        repo_root = Path(__file__).parent.parent.parent
        config_path = repo_root / "config" / "config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path.absolute()}"
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML configuration: {e}")

    if raw_config is None:
        raise ConfigError("Configuration file is empty")

    # Substitute environment variables
    try:
        raw_config = _substitute_env_variables(raw_config)
    except ConfigError:
        raise

    # Create Config object and validate
    config = Config(raw_config)
    config.validate()

    return config
