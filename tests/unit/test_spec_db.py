"""Unit tests for spec_db module."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from scripts.common.spec_db import Database, DatabaseError

try:
    from mysql.connector import Error as MySQLError
except ImportError:
    MySQLError = Exception


class TestDatabaseInit:
    """Tests for Database initialization."""

    def test_init_missing_required_keys(self):
        """Test initialization fails with missing required config keys."""
        with pytest.raises(DatabaseError, match="Missing database config keys"):
            Database({"host": "localhost"})

    def test_init_missing_host(self):
        """Test initialization fails without host."""
        with pytest.raises(DatabaseError, match="Missing database config keys"):
            Database({"user": "user", "database": "db"})

    def test_init_missing_user(self):
        """Test initialization fails without user."""
        with pytest.raises(DatabaseError, match="Missing database config keys"):
            Database({"host": "localhost", "database": "db"})

    def test_init_missing_database(self):
        """Test initialization fails without database name."""
        with pytest.raises(DatabaseError, match="Missing database config keys"):
            Database({"host": "localhost", "user": "user"})

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_init_success(self, mock_pool_class):
        """Test successful initialization."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        config = {
            "host": "localhost",
            "user": "testuser",
            "password": "testpass",
            "database": "testdb",
        }
        db = Database(config)

        assert db.config == config
        assert db.pool is not None
        mock_pool_class.assert_called_once()

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_init_pool_creation_failure(self, mock_pool_class):
        """Test initialization fails when pool creation fails."""
        mock_pool_class.side_effect = MySQLError("Connection failed")

        config = {
            "host": "localhost",
            "user": "testuser",
            "password": "testpass",
            "database": "testdb",
        }

        with pytest.raises(DatabaseError, match="Failed to initialize database pool"):
            Database(config)


class TestDatabaseQuery:
    """Tests for Database query methods."""

    @pytest.fixture
    def mock_db(self):
        """Create a mocked Database instance."""
        with patch("scripts.common.spec_db.pooling.MySQLConnectionPool"):
            return Database(
                {
                    "host": "localhost",
                    "user": "testuser",
                    "password": "testpass",
                    "database": "testdb",
                }
            )

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_query_success(self, mock_pool_class, mock_db):
        """Test successful SELECT query."""
        # Mock the connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "test"}]
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        result = mock_db.query("SELECT * FROM test WHERE id = %s", (1,))

        assert result == [{"id": 1, "name": "test"}]
        mock_connection.cursor.assert_called_once_with(dictionary=True)
        mock_cursor.execute.assert_called_once_with("SELECT * FROM test WHERE id = %s", (1,))

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_query_without_params(self, mock_pool_class, mock_db):
        """Test SELECT query without parameters."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        result = mock_db.query("SELECT * FROM test")

        assert result == []
        mock_cursor.execute.assert_called_once_with("SELECT * FROM test")

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_query_connection_error(self, mock_pool_class, mock_db):
        """Test query fails when connection error occurs."""
        mock_db.pool.get_connection.side_effect = MySQLError("Connection error")

        with pytest.raises(DatabaseError):
            mock_db.query("SELECT * FROM test")

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_get_one_with_results(self, mock_pool_class, mock_db):
        """Test get_one returns first result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "first"},
            {"id": 2, "name": "second"},
        ]
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        result = mock_db.get_one("SELECT * FROM test")

        assert result == {"id": 1, "name": "first"}

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_get_one_no_results(self, mock_pool_class, mock_db):
        """Test get_one returns None when no results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        result = mock_db.get_one("SELECT * FROM test WHERE id = %s", (999,))

        assert result is None


class TestDatabaseExecute:
    """Tests for Database execute methods."""

    @pytest.fixture
    def mock_db(self):
        """Create a mocked Database instance."""
        with patch("scripts.common.spec_db.pooling.MySQLConnectionPool"):
            return Database(
                {
                    "host": "localhost",
                    "user": "testuser",
                    "password": "testpass",
                    "database": "testdb",
                }
            )

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_execute_insert_success(self, mock_pool_class, mock_db):
        """Test successful INSERT query."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        result = mock_db.execute("INSERT INTO test (name) VALUES (%s)", ("test",))

        assert result == 1
        mock_cursor.execute.assert_called_once()
        mock_connection.commit.assert_called_once()

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_execute_update_success(self, mock_pool_class, mock_db):
        """Test successful UPDATE query."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        result = mock_db.execute("UPDATE test SET name = %s WHERE id = %s", ("new", 1))

        assert result == 5

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_execute_error_rollback(self, mock_pool_class, mock_db):
        """Test execute rolls back on error."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = MySQLError("Query error")
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        with pytest.raises(DatabaseError):
            mock_db.execute("INSERT INTO test (name) VALUES (%s)", ("test",))

        mock_connection.rollback.assert_called_once()

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_execute_many_success(self, mock_pool_class, mock_db):
        """Test successful executemany."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_db.pool.get_connection.return_value = mock_connection

        data = [("test1",), ("test2",), ("test3",)]
        result = mock_db.execute_many("INSERT INTO test (name) VALUES (%s)", data)

        assert result == 3
        mock_cursor.executemany.assert_called_once_with(
            "INSERT INTO test (name) VALUES (%s)", data
        )

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_execute_many_empty_data(self, mock_pool_class, mock_db):
        """Test executemany with empty data."""
        result = mock_db.execute_many("INSERT INTO test (name) VALUES (%s)", [])

        assert result == 0


class TestDatabaseContextManager:
    """Tests for Database context manager."""

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_context_manager(self, mock_pool_class):
        """Test Database works as context manager."""
        with patch("scripts.common.spec_db.pooling.MySQLConnectionPool"):
            with Database(
                {
                    "host": "localhost",
                    "user": "testuser",
                    "password": "testpass",
                    "database": "testdb",
                }
            ) as db:
                assert db is not None

    @patch("scripts.common.spec_db.pooling.MySQLConnectionPool")
    def test_close_method(self, mock_pool_class):
        """Test close method can be called."""
        with patch("scripts.common.spec_db.pooling.MySQLConnectionPool"):
            db = Database(
                {
                    "host": "localhost",
                    "user": "testuser",
                    "password": "testpass",
                    "database": "testdb",
                }
            )
            db.close()  # Should not raise
