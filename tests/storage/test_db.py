"""Tests for database connection management."""

import pytest

from storage import db
from storage.types import StorageError


SQLITE_CONFIG = {"engine": "sqlite", "database": ":memory:"}


@pytest.fixture(autouse=True)
def cleanup():
    """Ensure clean state before and after each test."""
    db.close()
    yield
    db.close()


class TestInit:
    """init() creates connection and tables."""

    def test_sqlite_creates_tables(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]
        assert "feature_history" in tables
        assert "repos" in tables
        assert "summaries" in tables

    def test_sqlite_tables_have_correct_count(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        count = cursor.fetchone()["cnt"]
        assert count == 3

    def test_idempotent_same_config(self):
        db.init(SQLITE_CONFIG)
        conn1 = db.get_connection()
        db.init(SQLITE_CONFIG)
        conn2 = db.get_connection()
        assert conn1 is conn2

    def test_invalid_engine_raises(self):
        with pytest.raises(StorageError, match="Invalid or missing engine"):
            db.init({"engine": "postgres"})

    def test_missing_engine_raises(self):
        with pytest.raises(StorageError, match="Invalid or missing engine"):
            db.init({"database": ":memory:"})

    def test_sqlite_missing_database_raises(self):
        with pytest.raises(StorageError, match="requires 'database' key"):
            db.init({"engine": "sqlite"})

    def test_mysql_missing_keys_raises(self):
        with pytest.raises(StorageError, match="missing required keys"):
            db.init({"engine": "mysql", "host": "localhost"})

    def test_mysql_missing_keys_lists_them(self):
        with pytest.raises(StorageError, match="database.*password.*user"):
            db.init({"engine": "mysql", "host": "localhost"})


class TestClose:
    """close() shuts down the connection."""

    def test_close_resets_state(self):
        db.init(SQLITE_CONFIG)
        db.close()
        with pytest.raises(StorageError, match="not initialized"):
            db.get_connection()

    def test_close_without_init_is_safe(self):
        db.close()  # should not raise

    def test_close_then_reinit(self):
        db.init(SQLITE_CONFIG)
        db.close()
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]
        assert "repos" in tables


class TestGetConnection:
    """get_connection() returns active connection or raises."""

    def test_before_init_raises(self):
        with pytest.raises(StorageError, match="not initialized"):
            db.get_connection()

    def test_after_init_returns_connection(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        assert conn is not None

    def test_connection_is_functional(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute("SELECT 1 as val")
        assert cursor.fetchone()["val"] == 1


class TestGetEngine:
    """get_engine() returns the engine name."""

    def test_before_init_raises(self):
        with pytest.raises(StorageError, match="not initialized"):
            db.get_engine()

    def test_sqlite_engine(self):
        db.init(SQLITE_CONFIG)
        assert db.get_engine() == "sqlite"

    def test_after_close_raises(self):
        db.init(SQLITE_CONFIG)
        db.close()
        with pytest.raises(StorageError, match="not initialized"):
            db.get_engine()


class TestSchemaIntegrity:
    """Schema creates correct table structures."""

    def test_repos_columns(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute("PRAGMA table_info(repos)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "id", "source", "source_id", "name", "url", "description",
            "raw_content", "source_metadata", "discovered_at",
            "first_featured_at", "last_featured_at", "feature_count",
        }
        assert columns == expected

    def test_summaries_columns(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute("PRAGMA table_info(summaries)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "id", "repo_id", "summary_type", "content",
            "model_used", "generated_at",
        }
        assert columns == expected

    def test_feature_history_columns(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute("PRAGMA table_info(feature_history)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {
            "id", "repo_id", "feature_type", "featured_date",
            "ranking_criteria",
        }
        assert columns == expected

    def test_repos_unique_constraint(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO repos (source, source_id, name, url, raw_content, source_metadata) "
            "VALUES ('github', '123', 'test/repo', 'https://github.com/test/repo', 'readme', '{}')"
        )
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO repos (source, source_id, name, url, raw_content, source_metadata) "
                "VALUES ('github', '123', 'test/repo2', 'https://github.com/test/repo2', 'readme2', '{}')"
            )

    def test_foreign_keys_enabled(self):
        db.init(SQLITE_CONFIG)
        conn = db.get_connection()
        cursor = conn.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
