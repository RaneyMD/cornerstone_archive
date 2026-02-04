"""Unit tests for spec_config module."""

import os
import pytest
import tempfile
from pathlib import Path

from scripts.common.spec_config import load_config, Config, ConfigError


class TestConfig:
    """Tests for Config class."""

    def test_config_dict_like_access(self):
        """Test that Config supports both dict and attribute access."""
        config = Config({"database": {"host": "localhost"}})
        assert config["database"]["host"] == "localhost"
        assert config.database["host"] == "localhost"

    def test_config_attribute_access_missing_key(self):
        """Test that accessing missing attribute raises AttributeError."""
        config = Config({"database": {}})
        with pytest.raises(AttributeError):
            _ = config.missing_key

    def test_config_validate_missing_sections(self):
        """Test validation fails when required sections are missing."""
        config = Config({"environment": "development"})
        with pytest.raises(ConfigError, match="Missing required configuration sections"):
            config.validate()

    def test_config_validate_invalid_environment(self):
        """Test validation fails with invalid environment."""
        config = Config(
            {
                "environment": "staging",
                "database": {"host": "localhost", "user": "user", "password": "pass", "database": "db"},
                "nas": {"root": "/path"},
                "logging": {},
            }
        )
        with pytest.raises(ConfigError, match="environment must be"):
            config.validate()

    def test_config_validate_missing_db_keys(self):
        """Test validation fails with missing database keys."""
        config = Config(
            {
                "environment": "development",
                "database": {"host": "localhost"},
                "nas": {"root": "/path"},
                "logging": {},
            }
        )
        with pytest.raises(ConfigError, match="Missing required database keys"):
            config.validate()

    def test_config_validate_missing_password(self):
        """Test validation fails when password is empty or placeholder."""
        config = Config(
            {
                "environment": "development",
                "database": {"host": "localhost", "user": "user", "password": "", "database": "db"},
                "nas": {"root": "/path"},
                "logging": {},
            }
        )
        with pytest.raises(ConfigError, match="password must be set"):
            config.validate()

    def test_config_validate_placeholder_password(self):
        """Test validation fails with unsubstituted environment variable."""
        config = Config(
            {
                "environment": "development",
                "database": {
                    "host": "localhost",
                    "user": "user",
                    "password": "${DB_PASSWORD}",
                    "database": "db",
                },
                "nas": {"root": "/path"},
                "logging": {},
            }
        )
        with pytest.raises(ConfigError, match="password must be set"):
            config.validate()

    def test_config_validate_invalid_logging_level(self):
        """Test validation fails with invalid logging level."""
        config = Config(
            {
                "environment": "development",
                "database": {
                    "host": "localhost",
                    "user": "user",
                    "password": "secret",
                    "database": "db",
                },
                "nas": {"root": "/path"},
                "logging": {"level": "INVALID"},
            }
        )
        with pytest.raises(ConfigError, match="logging.level must be"):
            config.validate()

    def test_config_validate_invalid_watcher_interval(self):
        """Test validation fails with invalid watcher scan interval."""
        config = Config(
            {
                "environment": "development",
                "database": {
                    "host": "localhost",
                    "user": "user",
                    "password": "secret",
                    "database": "db",
                },
                "nas": {"root": "/path"},
                "logging": {},
                "watcher": {"scan_interval_seconds": 0},
            }
        )
        with pytest.raises(ConfigError, match="scan_interval_seconds must be > 0"):
            config.validate()

    def test_config_validate_success(self):
        """Test validation succeeds with valid config."""
        config = Config(
            {
                "environment": "development",
                "database": {
                    "host": "localhost",
                    "user": "user",
                    "password": "secret",
                    "database": "db",
                },
                "nas": {"root": "/path"},
                "logging": {"level": "INFO"},
                "watcher": {"scan_interval_seconds": 30},
            }
        )
        config.validate()  # Should not raise


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_file_not_found(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_load_config_invalid_yaml(self):
        """Test error when YAML is invalid."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ConfigError, match="Failed to parse YAML"):
                load_config(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_config_empty_file(self):
        """Test error when config file is empty."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ConfigError, match="Configuration file is empty"):
                load_config(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_config_basic_valid(self):
        """Test loading a basic valid config."""
        config_content = """
environment: development
database:
  host: localhost
  user: testuser
  password: testpass
  database: testdb
nas:
  root: /nas/root
logging:
  level: INFO
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            f.flush()
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config["environment"] == "development"
            assert config["database"]["host"] == "localhost"
            assert config["nas"]["root"] == "/nas/root"
        finally:
            os.unlink(temp_path)

    def test_load_config_env_var_substitution(self):
        """Test environment variable substitution in config."""
        os.environ["TEST_DB_PASSWORD"] = "secret123"

        config_content = """
environment: development
database:
  host: localhost
  user: testuser
  password: ${TEST_DB_PASSWORD}
  database: testdb
nas:
  root: /nas/root
logging:
  level: INFO
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            f.flush()
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config["database"]["password"] == "secret123"
        finally:
            os.unlink(temp_path)
            del os.environ["TEST_DB_PASSWORD"]

    def test_load_config_env_var_with_default(self):
        """Test environment variable with default value."""
        # Make sure env var is not set
        os.environ.pop("NONEXISTENT_VAR", None)

        config_content = """
environment: development
database:
  host: localhost
  user: testuser
  password: ${NONEXISTENT_VAR:defaultpass}
  database: testdb
nas:
  root: /nas/root
logging:
  level: INFO
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            f.flush()
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config["database"]["password"] == "defaultpass"
        finally:
            os.unlink(temp_path)

    def test_load_config_missing_env_var_no_default(self):
        """Test error when required environment variable is not set."""
        os.environ.pop("MISSING_DB_PASSWORD", None)

        config_content = """
environment: development
database:
  host: localhost
  user: testuser
  password: ${MISSING_DB_PASSWORD}
  database: testdb
nas:
  root: /nas/root
logging:
  level: INFO
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ConfigError, match="Environment variable.*not set"):
                load_config(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_config_nested_env_var(self):
        """Test environment variable substitution in nested structures."""
        os.environ["API_TIMEOUT"] = "45"

        config_content = """
environment: development
database:
  host: localhost
  user: testuser
  password: testpass
  database: testdb
nas:
  root: /nas/root
logging:
  level: INFO
internet_archive:
  api_timeout_seconds: ${API_TIMEOUT}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            f.flush()
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config["internet_archive"]["api_timeout_seconds"] == "45"
        finally:
            os.unlink(temp_path)
            del os.environ["API_TIMEOUT"]

    def test_load_config_returns_config_object(self):
        """Test that load_config returns a Config object."""
        config_content = """
environment: development
database:
  host: localhost
  user: testuser
  password: testpass
  database: testdb
nas:
  root: /nas/root
logging:
  level: INFO
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            f.flush()
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert isinstance(config, Config)
            # Verify dict-like and attribute access work
            assert config["environment"] == "development"
            assert config.environment == "development"
        finally:
            os.unlink(temp_path)
