"""Tests for the FastAPI backend endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestRootEndpoint:
    """Tests for GET /"""

    def test_root_returns_status(self):
        """Test that root endpoint returns online status."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["service"] == "NPM Monitor API"
        assert "version" in data


class TestHealthEndpoint:
    """Tests for GET /health"""

    @patch("src.api.main.get_redis")
    @patch("src.database.is_database_available", return_value=True)
    def test_health_all_ok(self, mock_db_available, mock_get_redis):
        """Test healthy status when DB and Redis are available."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_get_redis.return_value = mock_redis

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["redis"] == "connected"

    @patch("src.api.main.get_redis")
    @patch("src.database.is_database_available", return_value=False)
    def test_health_db_unavailable(self, mock_db_available, mock_get_redis):
        """Test degraded status when DB is unavailable."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_get_redis.return_value = mock_redis

        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "unavailable"

    @patch("src.api.main.get_redis")
    @patch("src.database.is_database_available", return_value=True)
    def test_health_redis_unavailable(self, mock_db_available, mock_get_redis):
        """Test degraded status when Redis is unavailable."""
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Connection refused")
        mock_get_redis.return_value = mock_redis

        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert "error" in data["redis"]


class TestVersionEndpoint:
    """Tests for GET /version"""

    def test_version_returns_info(self):
        """Test that version endpoint returns project info."""
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "name" in data
        assert data["name"] == "npm-monitor"
        assert data["version"] == "0.1.0"


class TestStatsEndpoint:
    """Tests for GET /stats"""

    @patch("src.api.main.get_database_info")
    def test_stats_returns_data(self, mock_db_info):
        """Test that stats endpoint returns system statistics."""
        mock_db_info.return_value = {
            "total_rows": 12345,
            "blocked_count": 42,
            "table_size": "128 MB",
        }
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 12345
        assert data["blocked_count"] == 42
        assert data["table_size"] == "128 MB"
