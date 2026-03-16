"""Shared test fixtures for NPM Monitor."""

from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def mock_connection():
    """Create a mock database connection with cursor context manager."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return mock_conn, mock_cursor


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock_r = MagicMock()
    mock_r.ping.return_value = True
    mock_r.get.return_value = None
    mock_r.hgetall.return_value = {}
    mock_r.keys.return_value = []
    mock_pipe = MagicMock()
    mock_r.pipeline.return_value = mock_pipe
    return mock_r
