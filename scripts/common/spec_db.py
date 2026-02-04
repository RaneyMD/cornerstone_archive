"""Database connection and query utilities for Cornerstone Archive.

Provides MySQL connection management with connection pooling, query execution,
and graceful error handling with retry logic.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import mysql.connector
    from mysql.connector import pooling, Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception


logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Exception raised for database-related errors."""

    pass


class Database:
    """MySQL database connection manager with query utilities.

    Provides connection pooling, query execution, and automatic retry logic
    for transient failures.
    """

    def __init__(
        self,
        config: dict,
        pool_name: str = "cornerstone_archive",
        pool_size: int = 5,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        """Initialize database connection manager.

        Args:
            config: Dictionary with keys: host, user, password, database.
            pool_name: Name for connection pool.
            pool_size: Number of connections in pool.
            max_retries: Maximum number of retry attempts for transient errors.
            retry_delay_seconds: Base delay between retries (exponential backoff).

        Raises:
            DatabaseError: If connection cannot be established.
        """
        # Initialize pool first to avoid AttributeError in __del__
        self.pool = None
        self.connection = None

        if mysql is None:
            raise DatabaseError(
                "mysql-connector-python not installed. "
                "Run: pip install mysql-connector-python"
            )

        required_keys = {"host", "user", "database"}
        missing = required_keys - set(config.keys())
        if missing:
            raise DatabaseError(f"Missing database config keys: {', '.join(missing)}")

        self.config = config
        self.pool_name = pool_name
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize connection pool.

        Raises:
            DatabaseError: If pool cannot be created.
        """
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name=self.pool_name,
                pool_size=5,
                pool_reset_session=True,
                host=self.config["host"],
                user=self.config["user"],
                password=self.config.get("password", ""),
                database=self.config["database"],
            )
            logger.debug(f"Database pool initialized: {self.config['database']}")
        except MySQLError as e:
            raise DatabaseError(f"Failed to initialize database pool: {e}") from e

    def _get_connection(self) -> Any:
        """Get a connection from the pool with retry logic.

        Returns:
            MySQL database connection.

        Raises:
            DatabaseError: If connection cannot be obtained after max retries.
        """
        if self.pool is None:
            raise DatabaseError("Database pool not initialized")

        last_error = None
        for attempt in range(self.max_retries):
            try:
                connection = self.pool.get_connection()
                if attempt > 0:
                    logger.info(f"Database connection successful on attempt {attempt + 1}")
                return connection
            except MySQLError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay_seconds * (2 ** attempt)
                    logger.warning(
                        f"Database connection failed (attempt {attempt + 1}/"
                        f"{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

        raise DatabaseError(
            f"Could not connect to database after {self.max_retries} attempts: "
            f"{last_error}"
        )

    def query(
        self, sql: str, params: Optional[Tuple[Any, ...]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as list of dicts.

        Args:
            sql: SQL query string with %s placeholders for parameters.
            params: Tuple of parameter values to substitute in query.

        Returns:
            List of dictionaries (one per row).

        Raises:
            DatabaseError: If query fails.
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor(dictionary=True)

            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            results = cursor.fetchall()
            cursor.close()
            logger.debug(f"Query returned {len(results)} rows")
            return results

        except MySQLError as e:
            raise DatabaseError(f"Query failed: {e}") from e
        finally:
            if connection:
                connection.close()

    def get_one(
        self, sql: str, params: Optional[Tuple[Any, ...]] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return first result.

        Args:
            sql: SQL query string with %s placeholders for parameters.
            params: Tuple of parameter values to substitute in query.

        Returns:
            Dictionary representing first row, or None if no results.

        Raises:
            DatabaseError: If query fails.
        """
        results = self.query(sql, params)
        return results[0] if results else None

    def execute(
        self, sql: str, params: Optional[Tuple[Any, ...]] = None
    ) -> int:
        """Execute an INSERT, UPDATE, or DELETE query.

        Args:
            sql: SQL query string with %s placeholders for parameters.
            params: Tuple of parameter values to substitute in query.

        Returns:
            Number of rows affected.

        Raises:
            DatabaseError: If query fails.
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            affected_rows = cursor.rowcount
            connection.commit()
            cursor.close()

            logger.debug(f"Execute affected {affected_rows} rows")
            return affected_rows

        except MySQLError as e:
            if connection:
                connection.rollback()
            raise DatabaseError(f"Execute failed: {e}") from e
        finally:
            if connection:
                connection.close()

    def execute_many(
        self, sql: str, data: List[Tuple[Any, ...]]
    ) -> int:
        """Execute multiple INSERT/UPDATE/DELETE queries with different parameters.

        Args:
            sql: SQL query string with %s placeholders for parameters.
            data: List of parameter tuples.

        Returns:
            Total number of rows affected.

        Raises:
            DatabaseError: If any query fails.
        """
        if not data:
            return 0

        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            cursor.executemany(sql, data)
            affected_rows = cursor.rowcount
            connection.commit()
            cursor.close()

            logger.debug(f"Execute many affected {affected_rows} rows")
            return affected_rows

        except MySQLError as e:
            if connection:
                connection.rollback()
            raise DatabaseError(f"Execute many failed: {e}") from e
        finally:
            if connection:
                connection.close()

    def close(self) -> None:
        """Close the connection pool.

        Called automatically when context manager exits or during cleanup.
        """
        if self.pool:
            # Note: mysql-connector-python doesn't provide explicit pool closing
            # but connections are returned to pool when closed
            logger.debug("Database pool cleanup requested")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.close()
