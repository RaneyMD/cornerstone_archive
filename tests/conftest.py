"""Pytest configuration and fixtures."""
import pytest
import os
import yaml
from pathlib import Path


@pytest.fixture
def config():
    """Load development config for tests."""
    config_path = Path(__file__).parent.parent / "config" / "config.example.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def test_container_id():
    """Return a test container ID."""
    return 1


@pytest.fixture
def test_db_credentials(config):
    """Return test database credentials from config."""
    return {
        'host': config['database']['host'],
        'user': config['database']['user'],
        'password': config['database']['password'],
        'database': config['database']['database']
    }
