"""Tests for configuration validation."""

from unittest.mock import patch

from src.config import AppConfig, DatabaseConfig, app_config, db_config, validate_config


class TestDatabaseConfig:
    """Tests for DatabaseConfig dataclass."""

    def test_connection_string_format(self):
        """Test that connection string is properly formatted."""
        config = DatabaseConfig(host="localhost", port=5432, name="test_db", user="test_user", password="test_pass")
        assert "postgresql+psycopg://" in config.connection_string
        assert "test_user" in config.connection_string
        assert "localhost" in config.connection_string
        assert "5432" in config.connection_string
        assert "test_db" in config.connection_string

    def test_connection_string_url_encodes_password(self):
        """Test that special characters in password are URL-encoded."""
        config = DatabaseConfig(host="localhost", port=5432, name="db", user="user", password="p@ss w0rd!")
        # @ and space should be encoded
        assert "p%40ss" in config.connection_string
        assert "w0rd%21" in config.connection_string

    def test_psycopg_connection_string(self):
        """Test psycopg native connection string format."""
        config = DatabaseConfig(host="db.local", port=5433, name="mydb", user="admin", password="secret")
        connstr = config.psycopg_connection_string
        assert "host=db.local" in connstr
        assert "port=5433" in connstr
        assert "dbname=mydb" in connstr


class TestAppConfig:
    """Tests for AppConfig dataclass."""

    def test_default_values(self):
        """Test that defaults are sensible."""
        config = AppConfig()
        assert config.block_duration >= 60
        assert config.max_404_errors > 0
        assert config.retention_days >= 1

    def test_boolean_parsing(self):
        """Test boolean field parsing from strings."""
        with patch.dict("os.environ", {"ENABLE_BLOCKING": "false"}):
            config = AppConfig()
            assert config.enable_blocking is False

    def test_list_parsing(self):
        """Test suspicious paths are parsed as list."""
        config = AppConfig()
        assert isinstance(config.suspicious_paths, list)
        assert len(config.suspicious_paths) > 0


class TestValidateConfig:
    """Tests for the validate_config function."""

    def test_valid_config(self):
        """Test that a valid configuration produces no errors."""
        with patch.object(db_config, "password", "secure_password"), \
             patch.object(db_config, "host", "localhost"), \
             patch.object(db_config, "port", 5432), \
             patch.object(app_config, "enable_auth", False), \
             patch.object(app_config, "enable_cloudflare", False), \
             patch.object(app_config, "redis_url", "redis://localhost:6379/0"), \
             patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "retention_days", 30), \
             patch.object(app_config, "block_duration", 3600):
            errors = validate_config()
            assert len(errors) == 0

    def test_missing_db_password(self):
        """Test that missing DB password is flagged."""
        with patch.object(db_config, "password", ""), \
             patch.object(db_config, "host", "localhost"), \
             patch.object(db_config, "port", 5432), \
             patch.object(app_config, "enable_auth", False), \
             patch.object(app_config, "enable_cloudflare", False), \
             patch.object(app_config, "redis_url", "redis://localhost:6379"), \
             patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "retention_days", 30), \
             patch.object(app_config, "block_duration", 3600):
            errors = validate_config()
            assert any("DB_PASSWORD" in e for e in errors)

    def test_invalid_redis_url(self):
        """Test that invalid Redis URL format is flagged."""
        with patch.object(db_config, "password", "pass"), \
             patch.object(db_config, "host", "localhost"), \
             patch.object(db_config, "port", 5432), \
             patch.object(app_config, "enable_auth", False), \
             patch.object(app_config, "enable_cloudflare", False), \
             patch.object(app_config, "redis_url", "http://wrong-scheme:6379"), \
             patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "retention_days", 30), \
             patch.object(app_config, "block_duration", 3600):
            errors = validate_config()
            assert any("REDIS_URL" in e for e in errors)

    def test_smtp_missing_recipient(self):
        """Test that SMTP_TO is required when SMTP_HOST is set."""
        with patch.object(db_config, "password", "pass"), \
             patch.object(db_config, "host", "localhost"), \
             patch.object(db_config, "port", 5432), \
             patch.object(app_config, "enable_auth", False), \
             patch.object(app_config, "enable_cloudflare", False), \
             patch.object(app_config, "redis_url", "redis://localhost:6379"), \
             patch.object(app_config, "smtp_host", "smtp.example.com"), \
             patch.object(app_config, "smtp_to", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "retention_days", 30), \
             patch.object(app_config, "block_duration", 3600):
            errors = validate_config()
            assert any("SMTP_TO" in e for e in errors)

    def test_telegram_incomplete_config(self):
        """Test that Telegram token without chat_id is flagged."""
        with patch.object(db_config, "password", "pass"), \
             patch.object(db_config, "host", "localhost"), \
             patch.object(db_config, "port", 5432), \
             patch.object(app_config, "enable_auth", False), \
             patch.object(app_config, "enable_cloudflare", False), \
             patch.object(app_config, "redis_url", "redis://localhost:6379"), \
             patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "telegram_bot_token", "123:TOKEN"), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "retention_days", 30), \
             patch.object(app_config, "block_duration", 3600):
            errors = validate_config()
            assert any("TELEGRAM" in e for e in errors)

    def test_invalid_port(self):
        """Test that an invalid port number is flagged."""
        with patch.object(db_config, "password", "pass"), \
             patch.object(db_config, "host", "localhost"), \
             patch.object(db_config, "port", 99999), \
             patch.object(app_config, "enable_auth", False), \
             patch.object(app_config, "enable_cloudflare", False), \
             patch.object(app_config, "redis_url", "redis://localhost:6379"), \
             patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "retention_days", 30), \
             patch.object(app_config, "block_duration", 3600):
            errors = validate_config()
            assert any("DB_PORT" in e for e in errors)

    def test_auth_weak_password(self):
        """Test that a short auth password is flagged."""
        with patch.object(db_config, "password", "pass"), \
             patch.object(db_config, "host", "localhost"), \
             patch.object(db_config, "port", 5432), \
             patch.object(app_config, "enable_auth", True), \
             patch.object(app_config, "auth_password", "short"), \
             patch.object(app_config, "enable_cloudflare", False), \
             patch.object(app_config, "redis_url", "redis://localhost:6379"), \
             patch.object(app_config, "smtp_host", ""), \
             patch.object(app_config, "telegram_bot_token", ""), \
             patch.object(app_config, "telegram_chat_id", ""), \
             patch.object(app_config, "retention_days", 30), \
             patch.object(app_config, "block_duration", 3600):
            errors = validate_config()
            assert any("AUTH_PASSWORD" in e and "8 characters" in e for e in errors)
