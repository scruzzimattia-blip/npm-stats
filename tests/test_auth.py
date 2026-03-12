"""Tests for authentication module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from ipaddress import ip_address, ip_network


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
        mock_st.session_state = {"authenticated": True}

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
        mock_st.session_state = {}
        mock_st.container = MagicMock
        mock_st.columns = Mock(return_value=[Mock(), Mock(), Mock()])
        mock_st.text_input = Mock(side_effect=["admin", "password123"])
        mock_st.button = Mock(return_value=True)
        mock_st.rerun = Mock()

        with patch.object(app_config, "enable_auth", True):
            with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
                with patch.object(app_config, "auth_username", "admin"):
                    with patch.object(app_config, "auth_password", "password123"):
                        result = check_auth()
                        assert result is True
                        mock_st.rerun.assert_called_once()

    @patch("src.auth.st")
    def test_check_auth_invalid_credentials(self, mock_st):
        """Test failed login with invalid credentials."""
        from src.auth import check_auth
        from src.config import app_config

        mock_st._client_ip = "192.168.1.100"
        mock_st.session_state = {}
        mock_st.container = MagicMock
        mock_st.columns = Mock(return_value=[Mock(), Mock(), Mock()])
        mock_st.text_input = Mock(side_effect=["admin", "wrongpassword"])
        mock_st.button = Mock(return_value=True)
        mock_st.error = Mock()

        with patch.object(app_config, "enable_auth", True):
            with patch.object(app_config, "allowed_networks", ["192.168.1.0/24"]):
                with patch.object(app_config, "auth_username", "admin"):
                    with patch.object(app_config, "auth_password", "password123"):
                        result = check_auth()
                        assert result is False
                        mock_st.error.assert_called_once()
