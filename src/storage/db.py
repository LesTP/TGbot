"""
Database connection management for the Storage module.

Provides init/close lifecycle and an internal get_connection() for
use by other storage submodules. Supports SQLite (dev/test) and
MySQL (production) engines.
"""

import os
import sqlite3
from pathlib import Path

from storage.types import StorageError

_connection = None
_engine = None

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_REQUIRED_MYSQL_KEYS = {"host", "user", "password", "database"}


def init(config: dict) -> None:
    """Initialize the storage connection and create tables.

    Config shapes:
      SQLite: {"engine": "sqlite", "database": ":memory:" or "path/to/file.db"}
      MySQL:  {"engine": "mysql", "host": ..., "user": ..., "password": ..., "database": ...}

    Idempotent — safe to call multiple times with the same config.
    """
    global _connection, _engine

    if _connection is not None:
        return

    engine = config.get("engine")
    if engine not in ("sqlite", "mysql"):
        raise StorageError(
            f"Invalid or missing engine: {engine!r}. Must be 'sqlite' or 'mysql'."
        )

    if engine == "sqlite":
        database = config.get("database")
        if not database:
            raise StorageError("SQLite config requires 'database' key.")
        _connection = sqlite3.connect(database)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")

    elif engine == "mysql":
        missing = _REQUIRED_MYSQL_KEYS - set(config.keys())
        if missing:
            raise StorageError(
                f"MySQL config missing required keys: {', '.join(sorted(missing))}"
            )
        try:
            import mysql.connector

            _connection = mysql.connector.connect(
                host=config["host"],
                user=config["user"],
                password=config["password"],
                database=config["database"],
            )
        except ImportError:
            raise StorageError(
                "mysql-connector-python is not installed. "
                "Install it with: pip install mysql-connector-python"
            )
        except Exception as e:
            raise StorageError(f"MySQL connection failed: {e}")

    _engine = engine
    _run_schema()


def close() -> None:
    """Close the storage connection."""
    global _connection, _engine

    if _connection is not None:
        _connection.close()
        _connection = None
        _engine = None


def get_connection():
    """Return the active connection. Internal use by storage submodules."""
    if _connection is None:
        raise StorageError("Storage not initialized. Call init() first.")
    return _connection


def get_engine() -> str:
    """Return the active engine name ('sqlite' or 'mysql')."""
    if _engine is None:
        raise StorageError("Storage not initialized. Call init() first.")
    return _engine


def _run_schema() -> None:
    """Execute schema DDL to create tables if they don't exist."""
    schema_sql = _SCHEMA_PATH.read_text()

    if _engine == "mysql":
        schema_sql = schema_sql.replace("AUTOINCREMENT", "AUTO_INCREMENT")

    if _engine == "sqlite":
        _connection.executescript(schema_sql)
    else:
        cursor = _connection.cursor()
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        _connection.commit()
        cursor.close()
