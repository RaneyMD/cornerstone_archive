# Testing

Tests are organized by layer:

- `unit/` — Test individual functions in isolation
- `integration/` — Test watcher + database + NAS together
- `e2e/` — Test full pipeline for one container
- `fixtures/` — Sample data for testing

## Running Tests
```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_spec_db.py

# Specific test
pytest tests/unit/test_spec_db.py::test_get_connection

# With coverage
pytest --cov=scripts --cov-report=html

# Verbose output
pytest -v
```

## Writing Tests

See existing tests for examples. Use the Arrange-Act-Assert pattern:
```python
def test_example():
    """Test description."""
    # Arrange
    data = {"key": "value"}
    
    # Act
    result = some_function(data)
    
    # Assert
    assert result == expected
```
