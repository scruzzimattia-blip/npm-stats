"""Tests for the notification module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

from src.config import app_config


class TestSendNotification:
    """Tests for the send_notification function."""

    @patch("src.notifications.urllib.request.urlopen")
    def test_send_notification_webhook_discord(self, mock_urlopen):
        """Test Discord webhook notification."""
        from src.notifications import send_notification

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        block_until = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch.object(app_config, "notify_on_block", True), \
             patch.object(app_config, "webhook_url", "https://discord.com/api/webhooks/test"), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "ntfy_topic", ""), \
             patch.object(app_config, "smtp_host", ""):
            result = send_notification("1.2.3.4", "Test reason", block_until)
            assert result is True
            mock_urlopen.assert_called_once()

    @patch("src.notifications.urllib.request.urlopen")
    def test_send_notification_telegram(self, mock_urlopen):
        """Test Telegram notification."""
        from src.notifications import send_notification

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        block_until = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch.object(app_config, "notify_on_block", True), \
             patch.object(app_config, "webhook_url", ""), \
             patch.object(app_config, "telegram_bot_token", "123:BOT_TOKEN"), \
             patch.object(app_config, "telegram_chat_id", "987654"), \
             patch.object(app_config, "ntfy_topic", ""), \
             patch.object(app_config, "smtp_host", ""):
            result = send_notification("1.2.3.4", "Test reason", block_until)
            assert result is True

    def test_send_notification_disabled(self):
        """Test that notifications are skipped when disabled."""
        from src.notifications import send_notification

        block_until = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch.object(app_config, "notify_on_block", False):
            result = send_notification("1.2.3.4", "Test reason", block_until)
            assert result is False

    def test_send_notification_no_channels(self):
        """Test that notifications return False when no channels configured."""
        from src.notifications import send_notification

        block_until = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch.object(app_config, "notify_on_block", True), \
             patch.object(app_config, "webhook_url", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "ntfy_topic", ""), \
             patch.object(app_config, "smtp_host", ""):
            result = send_notification("1.2.3.4", "Test reason", block_until)
            assert result is False


class TestSendNtfyNotification:
    """Tests for ntfy.sh notifications."""

    @patch("src.notifications.urllib.request.urlopen")
    def test_send_ntfy_success(self, mock_urlopen):
        """Test successful ntfy notification."""
        from src.notifications import send_ntfy_notification

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        with patch.object(app_config, "ntfy_topic", "test-topic"), \
             patch.object(app_config, "ntfy_url", "https://ntfy.sh"), \
             patch.object(app_config, "ntfy_priority", "default"):
            result = send_ntfy_notification("Test Title", "Test Message", "high")
            assert result is True

    def test_send_ntfy_no_topic(self):
        """Test ntfy returns False when no topic configured."""
        from src.notifications import send_ntfy_notification

        with patch.object(app_config, "ntfy_topic", ""):
            result = send_ntfy_notification("Test", "Message")
            assert result is False


class TestSendEmailNotification:
    """Tests for email notifications."""

    @patch("src.notifications.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp_class):
        """Test successful email notification."""
        from src.notifications import send_email_notification

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        with patch.object(app_config, "smtp_host", "smtp.example.com"), \
             patch.object(app_config, "smtp_port", 587), \
             patch.object(app_config, "smtp_user", "user"), \
             patch.object(app_config, "smtp_password", "pass"), \
             patch.object(app_config, "smtp_from", "from@example.com"), \
             patch.object(app_config, "smtp_to", "to@example.com"):
            send_email_notification("Test Subject", "Test Body")
            mock_server.send_message.assert_called_once()

    def test_send_email_no_config(self):
        """Test email does nothing when not configured."""
        from src.notifications import send_email_notification

        with patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "smtp_to", ""):
            # Should return without error
            send_email_notification("Test", "Body")


class TestSendTestNotification:
    """Tests for test notification function."""

    def test_send_test_no_channels(self):
        """Test that test notification returns False when nothing is configured."""
        from src.notifications import send_test_notification

        with patch.object(app_config, "webhook_url", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "ntfy_topic", ""), \
             patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "smtp_to", ""), \
             patch.object(app_config, "notify_on_block", True):
            result = send_test_notification()
            assert result is False
