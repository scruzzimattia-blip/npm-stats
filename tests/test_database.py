"""Tests for database operations."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return mock_conn, mock_cursor


def test_insert_traffic_batch_empty():
    """Test batch insert with empty data."""
    from src.database import insert_traffic_batch

    result = insert_traffic_batch([])
    assert result == 0


@patch("src.database.get_connection")
def test_insert_traffic_batch_success(mock_get_connection, mock_connection):
    """Test successful batch insert."""
    from src.database import insert_traffic_batch

    mock_conn, mock_cursor = mock_connection
    mock_get_connection.return_value = mock_conn

    rows = [
        (datetime.now(), "example.com", "GET", "/path", 200, "1.2.3.4", "Mozilla", None, 1024, None, None, "https"),
        (datetime.now(), "example.com", "POST", "/api", 201, "1.2.3.4", "Mozilla", None, 512, None, None, "https"),
    ]

    result = insert_traffic_batch(rows)

    assert result == 2


@patch("src.database.get_connection")
def test_cleanup_old_data(mock_get_connection, mock_connection):
    """Test cleanup of old data."""
    from src.database import cleanup_old_data

    mock_conn, mock_cursor = mock_connection
    mock_get_connection.return_value = mock_conn
    mock_cursor.rowcount = 100

    result = cleanup_old_data(30)

    assert result == 100
    assert mock_cursor.execute.called


@patch("src.database.get_connection")
def test_get_newest_timestamp(mock_get_connection, mock_connection):
    """Test getting newest timestamp."""
    from src.database import get_newest_timestamp

    mock_conn, mock_cursor = mock_connection
    mock_get_connection.return_value = mock_conn

    test_time = datetime(2024, 1, 1, 12, 0, 0)
    mock_cursor.fetchone.return_value = (test_time,)

    result = get_newest_timestamp()

    assert result == test_time


@patch("src.database.get_connection")
def test_get_newest_timestamp_empty(mock_get_connection, mock_connection):
    """Test getting newest timestamp from empty database."""
    from src.database import get_newest_timestamp

    mock_conn, mock_cursor = mock_connection
    mock_get_connection.return_value = mock_conn
    mock_cursor.fetchone.return_value = None

    result = get_newest_timestamp()

    assert result is None


@patch("src.database.get_connection")
def test_get_distinct_hosts(mock_get_connection, mock_connection):
    """Test getting distinct hosts."""
    from src.database import get_distinct_hosts

    mock_conn, mock_cursor = mock_connection
    mock_get_connection.return_value = mock_conn
    mock_cursor.fetchall.return_value = [("example.com",), ("test.com",)]

    result = get_distinct_hosts()

    assert result == ["example.com", "test.com"]


def test_database_config():
    """Test database configuration."""
    from src.config import DatabaseConfig

    config = DatabaseConfig(host="localhost", port=5432, name="test_db", user="test_user", password="test_pass")

    assert config.host == "localhost"
    assert config.port == 5432
    assert config.name == "test_db"
    assert "postgresql" in config.connection_string


def test_app_config():
    """Test application configuration."""
    from src.config import AppConfig

    config = AppConfig(log_dir="/logs", lines_per_file=10000, max_display_rows=50000, retention_days=30)

    assert config.log_dir == "/logs"
    assert config.lines_per_file == 10000
    assert config.max_display_rows == 50000
    assert config.retention_days == 30
