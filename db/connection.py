"""Singleton database connection manager for SQLite."""

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "portfolio_database.db"


class DatabaseManager:
    """Singleton SQLite connection manager.

    All database access in the application goes through this class.
    Uses sqlite3.Row for dict-like row access.
    """

    _instance: "DatabaseManager | None" = None
    _connection: sqlite3.Connection | None = None

    def __new__(cls, db_path: Path = DB_PATH) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db_path = db_path
        return cls._instance

    def get_connection(self) -> sqlite3.Connection:
        """Return the shared SQLite connection, creating it if needed."""
        if self._connection is None:
            logger.info("Opening SQLite connection to %s", self._db_path)
            self._connection = sqlite3.connect(
                str(self._db_path), check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def execute_query(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """Execute a SELECT query and return results as a list of dicts.

        Args:
            sql: The SQL SELECT statement to execute.
            params: Optional parameters for parameterized queries.

        Returns:
            List of dicts, one per row, keyed by column name.

        Raises:
            sqlite3.OperationalError: If the SQL is invalid.
        """
        conn = self.get_connection()
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def execute_script(self, script: str) -> None:
        """Execute a multi-statement SQL script (e.g. schema creation)."""
        conn = self.get_connection()
        conn.executescript(script)
        logger.info("Executed SQL script successfully")

    def close(self) -> None:
        """Close the database connection and reset the singleton."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("Closed SQLite connection")
        DatabaseManager._instance = None
