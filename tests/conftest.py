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
def test_db_credentials():
    """Return test database credentials."""
    return {
        'host': os.getenv('TEST_DB_HOST', 'cornerstonearchive.raneyworld.com'),
        'user': os.getenv('TEST_DB_USER', 'raneywor_csa_dev'),
        'password': os.getenv('TEST_DB_PASSWORD', 'test_password'),
        'database': os.getenv('TEST_DB_NAME', 'raneywor_csa_dev_state')
    }
