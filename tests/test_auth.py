"""Tests for authentication module."""

from unittest.mock import MagicMock, Mock, patch

import pytest


# Mock database at module level to prevent connection attempts
@pytest.fixture(autouse=True)
def mock_database():
    with patch("src.database.get_connection") as mock_get_conn, patch("src.database.init_database"):
        # Create a proper mock connection with cursor context manager
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = None
        mock_get_conn.return_value = mock_conn
        yield mock_get_conn


class TestCheckIPAccess:
    """Tests for IP access checking."""

    @patch("src.auth.st")
    def test_check_ip_access_no_restrictions(self, mock_st):
        """Test access when no networks are configured."""
        from src.auth import check_ip_access
        from src.config import app_config

        with patch.object(app_config, "allowed_networks", []):
            result = check_ip_access()
            assert result is True

    @patch("src.auth.st")
    def test_check_ip_access_allowed_network(self, mock_st):
        """Test access from allowed network."""
        from src.auth import check_ip_access
        from src.config import app_config

        mock_st._client_ip = "192.168.1.100"

        with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
            result = check_ip_access()
            assert result is True

    @patch("src.auth.st")
    def test_check_ip_access_denied_network(self, mock_st):
        """Test access denied from non-allowed network."""
        from src.auth import check_ip_access
        from src.config import app_config

        mock_st._client_ip = "10.0.0.1"

        with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
            result = check_ip_access()
            assert result is False

    @patch("src.auth.st")
    def test_check_ip_access_invalid_network(self, mock_st):
        """Test handling of invalid network configuration."""
        from src.auth import check_ip_access
        from src.config import app_config

        mock_st._client_ip = "192.168.1.100"

        with patch.object(app_config, "allowed_networks", ["invalid-network", "192.168.1.0/24"]):
            result = check_ip_access()
            assert result is True


class TestCheckAuth:
    """Tests for authentication checking."""

    @patch("src.auth.st")
    def test_check_auth_disabled(self, mock_st):
        """Test when authentication is disabled."""
        from src.auth import check_auth
        from src.config import app_config

        with patch.object(app_config, "enable_auth", False):
            result = check_auth()
            assert result is True

    @patch("src.auth.st")
    def test_check_auth_ip_denied(self, mock_st):
        """Test authentication with denied IP."""
        from src.auth import check_auth
        from src.config import app_config

        mock_st._client_ip = "10.0.0.1"
        mock_st.session_state = {}
        mock_st.error = Mock()

        with patch.object(app_config, "enable_auth", True):
            with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
                result = check_auth()
                assert result is False
                mock_st.error.assert_called_once()

    @patch("src.auth.st")
    def test_check_auth_already_authenticated(self, mock_st):
        """Test when user is already authenticated."""
        from src.auth import check_auth
        from src.config import app_config

        mock_st._client_ip = "192.168.1.100"

        # Use a dict-like object that supports attribute access
        class SessionState(dict):
            def __getattr__(self, key):
                return self.get(key)

            def __setattr__(self, key, value):
                self[key] = value

        mock_st.session_state = SessionState({"authenticated": True})

        with patch.object(app_config, "enable_auth", True):
            with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
                result = check_auth()
                assert result is True

    @patch("src.auth.st")
    def test_check_auth_valid_credentials(self, mock_st):
        """Test successful login with valid credentials."""
        from src.auth import check_auth
        from src.config import app_config

        mock_st._client_ip = "192.168.1.100"

        # Use a dict-like object that supports attribute access
        class SessionState(dict):
            def __getattr__(self, key):
                return self.get(key)

            def __setattr__(self, key, value):
                self[key] = value

        mock_st.session_state = SessionState({})
        # Mock container and columns as context managers
        mock_container = MagicMock()
        mock_container.__enter__ = Mock(return_value=mock_container)
        mock_container.__exit__ = Mock(return_value=False)
        mock_st.container.return_value = mock_container
        mock_col = MagicMock()
        mock_col.__enter__ = Mock(return_value=mock_col)
        mock_col.__exit__ = Mock(return_value=False)
        mock_st.columns.return_value = [mock_col, mock_col, mock_col]
        mock_st.text_input = Mock(side_effect=["admin", "password123", ""])
        mock_st.button = Mock(return_value=True)
        mock_st.rerun = Mock()

        with patch.object(app_config, "enable_auth", True):
            with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
                with patch.object(app_config, "auth_username", "admin"):
                    with patch.object(app_config, "auth_password", "password123"):
                        with patch("src.auth._check_rate_limit", return_value=(True, 0)):
                            with patch("src.auth._record_successful_attempt"):
                                with patch("src.auth.get_user") as mock_get_user:
                                    mock_get_user.return_value = {
                                        "username": "admin",
                                        "password_hash": "test_hash",
                                        "role": "admin",
                                    }
                                    with patch("src.auth.verify_password", return_value=True):
                                        with patch("src.auth.hash_password", return_value="test_hash"):
                                            with patch("src.database.add_to_whitelist"):
                                                with patch("src.blocking.get_blocker") as mock_blocker:
                                                    mock_blocker.return_value.whitelist_ip = Mock()
                                                    check_auth()
                                                    mock_st.rerun.assert_called_once()

    @patch("src.auth.st")
    def test_check_auth_invalid_credentials(self, mock_st):
        """Test failed login with invalid credentials."""
        from src.auth import check_auth
        from src.config import app_config

        mock_st._client_ip = "192.168.1.100"

        # Use a dict-like object that supports attribute access
        class SessionState(dict):
            def __getattr__(self, key):
                return self.get(key)

            def __setattr__(self, key, value):
                self[key] = value

        mock_st.session_state = SessionState({})
        # Mock container and columns as context managers
        mock_container = MagicMock()
        mock_container.__enter__ = Mock(return_value=mock_container)
        mock_container.__exit__ = Mock(return_value=False)
        mock_st.container.return_value = mock_container
        mock_col = MagicMock()
        mock_col.__enter__ = Mock(return_value=mock_col)
        mock_col.__exit__ = Mock(return_value=False)
        mock_st.columns.return_value = [mock_col, mock_col, mock_col]
        mock_st.text_input = Mock(side_effect=["admin", "wrongpassword", ""])
        mock_st.button = Mock(return_value=True)
        mock_st.error = Mock()

        with patch.object(app_config, "enable_auth", True):
            with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
                with patch.object(app_config, "auth_username", "admin"):
                    with patch.object(app_config, "auth_password", "password123"):
                        with patch("src.auth._check_rate_limit", return_value=(True, 0)):
                            with patch("src.auth._record_failed_attempt"):
                                result = check_auth()
                                assert result is False
                                mock_st.error.assert_called_once()
