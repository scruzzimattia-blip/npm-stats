"""Configuration module for NPM Monitor."""

import ipaddress
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "npm_monitor"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "npm_user"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    pool_min_conn: int = field(default_factory=lambda: int(os.getenv("DB_POOL_MIN", "1")))
    pool_max_conn: int = field(default_factory=lambda: int(os.getenv("DB_POOL_MAX", "10")))

    @property
    def connection_string(self) -> str:
        password = quote_plus(self.password)
        return f"postgresql+psycopg://{self.user}:{password}@{self.host}:{self.port}/{self.name}"

    @property
    def psycopg_connection_string(self) -> str:
        return f"host={self.host} port={self.port} dbname={self.name} user={self.user} password={self.password}"


@dataclass
class AppConfig:
    """Application configuration."""

    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "/var/log/npm"))
    lines_per_file: int = field(default_factory=lambda: int(os.getenv("LINES_PER_FILE", "10000")))
    max_display_rows: int = field(default_factory=lambda: int(os.getenv("MAX_DISPLAY_ROWS", "50000")))
    retention_days: int = field(default_factory=lambda: int(os.getenv("RETENTION_DAYS", "30")))
    enable_geoip: bool = field(default_factory=lambda: os.getenv("ENABLE_GEOIP", "false").lower() == "true")
    geoip_db_path: str = field(default_factory=lambda: os.getenv("GEOIP_DB_PATH", "/usr/share/GeoIP/GeoLite2-City.mmdb"))
    enable_auth: bool = field(default_factory=lambda: os.getenv("ENABLE_AUTH", "false").lower() == "true")
    auth_username: str = field(default_factory=lambda: os.getenv("AUTH_USERNAME", "admin"))
    auth_password: str = field(default_factory=lambda: os.getenv("AUTH_PASSWORD", ""))
    allowed_networks: List[str] = field(default_factory=lambda: os.getenv("ALLOWED_NETWORKS", "127.0.0.1/32").split(","))
    # Database and Caching
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    
    # Blocking configuration
    enable_blocking: bool = field(default_factory=lambda: os.getenv("ENABLE_BLOCKING", "true").lower() == "true")
    block_duration: int = field(default_factory=lambda: int(os.getenv("BLOCK_DURATION", "3600")))  # 1 hour
    max_404_errors: int = field(default_factory=lambda: int(os.getenv("MAX_404_ERRORS", "20")))  # per 5 minutes
    max_403_errors: int = field(default_factory=lambda: int(os.getenv("MAX_403_ERRORS", "10")))  # per 5 minutes
    max_5xx_errors: int = field(default_factory=lambda: int(os.getenv("MAX_5XX_ERRORS", "50")))  # per 5 minutes
    max_failed_requests: int = field(default_factory=lambda: int(os.getenv("MAX_FAILED_REQUESTS", "100")))  # per 5 minutes
    max_requests_per_minute: int = field(default_factory=lambda: int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60")))
    suspicious_paths: List[str] = field(
        default_factory=lambda: [
            p.strip()
            for p in os.getenv(
                "SUSPICIOUS_PATHS",
                "/wp-admin,/wp-login.php,/phpmyadmin,/admin,/login,.env,.git,/config.php,/backup,/sql",
            ).split(",")
            if p.strip()
        ]
    )
    sensitive_paths: List[str] = field(
        default_factory=lambda: [
            p.strip()
            for p in os.getenv(
                "SENSITIVE_PATHS",
                "/login,/admin,/api/auth,/config,/setup,/install,/manage,/db-admin",
            ).split(",")
            if p.strip()
        ]
    )
    max_suspicious_paths: int = field(default_factory=lambda: int(os.getenv("MAX_SUSPICIOUS_PATHS", "5")))
    honey_paths: List[str] = field(
        default_factory=lambda: [
            p.strip()
            for p in os.getenv(
                "HONEY_PATHS",
                "/.env,/.git/config,/wp-config.php,/config.php,/backup.sql,/dump.sql",
            ).split(",")
            if p.strip()
        ]
    )
    use_firewall: bool = field(default_factory=lambda: os.getenv("USE_FIREWALL", "false").lower() == "true")
    honey_pot_duration: int = field(default_factory=lambda: int(os.getenv("HONEY_POT_DURATION", "31536000")))  # Default: 1 year in seconds
    blocked_countries: List[str] = field(default_factory=lambda: [c.strip().upper() for c in os.getenv("BLOCKED_COUNTRIES", "").split(",") if c.strip()])
    allow_only_countries: List[str] = field(default_factory=lambda: [c.strip().upper() for c in os.getenv("ALLOW_ONLY_COUNTRIES", "").split(",") if c.strip()])
    # Cloudflare settings
    enable_cloudflare: bool = field(default_factory=lambda: os.getenv("ENABLE_CLOUDFLARE", "false").lower() == "true")
    cloudflare_api_token: str = field(default_factory=lambda: os.getenv("CLOUDFLARE_API_TOKEN", ""))
    cloudflare_zone_id: str = field(default_factory=lambda: os.getenv("CLOUDFLARE_ZONE_ID", ""))
    # Anomaly detection
    enable_anomaly_detection: bool = field(default_factory=lambda: os.getenv("ENABLE_ANOMALY_DETECTION", "true").lower() == "true")
    spike_threshold_factor: float = field(default_factory=lambda: float(os.getenv("SPIKE_THRESHOLD_FACTOR", "3.0")))
    spike_min_requests: int = field(default_factory=lambda: int(os.getenv("SPIKE_MIN_REQUESTS", "50")))
    # CrowdSec settings
    enable_crowdsec: bool = field(default_factory=lambda: os.getenv("ENABLE_CROWDSEC", "false").lower() == "true")
    crowdsec_api_url: str = field(default_factory=lambda: os.getenv("CROWDSEC_API_URL", "http://localhost:8080"))
    crowdsec_api_key: str = field(default_factory=lambda: os.getenv("CROWDSEC_API_KEY", ""))
    # Notification settings
    webhook_url: str = field(default_factory=lambda: os.getenv("WEBHOOK_URL", ""))
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    notify_on_block: bool = field(default_factory=lambda: os.getenv("NOTIFY_ON_BLOCK", "true").lower() == "true")
    # ntfy.sh settings
    ntfy_url: str = field(default_factory=lambda: os.getenv("NTFY_URL", "https://ntfy.sh"))
    ntfy_topic: str = field(default_factory=lambda: os.getenv("NTFY_TOPIC", ""))
    ntfy_priority: str = field(default_factory=lambda: os.getenv("NTFY_PRIORITY", "default"))
    # Email / SMTP settings
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", "npm-monitor@example.com"))
    smtp_to: str = field(default_factory=lambda: os.getenv("SMTP_TO", ""))
    # AI settings
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    ai_model: str = field(default_factory=lambda: os.getenv("AI_MODEL", "google/gemini-2.0-flash-lite:free"))
    enable_ai_auto_analysis: bool = field(default_factory=lambda: os.getenv("ENABLE_AI_AUTO_ANALYSIS", "false").lower() == "true")
    # NPM Database settings (for auto-discovery)
    npm_db_type: str = field(default_factory=lambda: os.getenv("NPM_DB_TYPE", "mysql"))  # mysql or sqlite
    npm_db_host: str = field(default_factory=lambda: os.getenv("NPM_DB_HOST", "localhost"))
    npm_db_port: int = field(default_factory=lambda: int(os.getenv("NPM_DB_PORT", "3306")))
    npm_db_user: str = field(default_factory=lambda: os.getenv("NPM_DB_USER", "npm"))
    npm_db_password: str = field(default_factory=lambda: os.getenv("NPM_DB_PASSWORD", ""))
    npm_db_name: str = field(default_factory=lambda: os.getenv("NPM_DB_NAME", "npm"))
    npm_db_sqlite_path: str = field(default_factory=lambda: os.getenv("NPM_DB_SQLITE_PATH", "/data/database.sqlite"))
    _last_load_time: float = field(default=0.0, init=False)

    def load_dynamic_settings(self, force: bool = False):
        """Load settings from database to override environment variables (cached for 60s)."""
        import time
        now = time.time()
        if not force and now - self._last_load_time < 60:
            return

        try:
            from .database import get_all_settings
            db_settings = get_all_settings()
            
            # Map DB keys to attribute names
            for key, value in db_settings.items():
                if hasattr(self, key):
                    attr_type = type(getattr(self, key))
                    if attr_type == bool:
                        setattr(self, key, value.lower() == "true")
                    elif attr_type == int:
                        setattr(self, key, int(value))
                    elif attr_type == list:
                        setattr(self, key, [p.strip() for p in value.split(",") if p.strip()])
                    else:
                        setattr(self, key, value)
            self._last_load_time = now
        except Exception:
            # Database might not be ready yet
            pass


# Performance settings
QUERY_TIMEOUT: int = int(os.getenv("QUERY_TIMEOUT", "30"))  # Database query timeout in seconds
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # Cache time-to-live in seconds
MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", str(min(8, os.cpu_count() or 4))))  # Parallel workers
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "65536"))  # File read chunk size in bytes

# Private IP networks to filter out
PRIVATE_NETWORKS: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),  # Link-local
]

# Cloudflare IP ranges (updated)
CLOUDFLARE_NETWORKS: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("173.245.48.0/20"),
    ipaddress.ip_network("103.21.244.0/22"),
    ipaddress.ip_network("103.22.200.0/22"),
    ipaddress.ip_network("103.31.4.0/22"),
    ipaddress.ip_network("141.101.64.0/18"),
    ipaddress.ip_network("108.162.192.0/18"),
    ipaddress.ip_network("190.93.240.0/20"),
    ipaddress.ip_network("188.114.96.0/20"),
    ipaddress.ip_network("197.234.240.0/22"),
    ipaddress.ip_network("198.41.128.0/17"),
    ipaddress.ip_network("162.158.0.0/15"),
    ipaddress.ip_network("104.16.0.0/13"),
    ipaddress.ip_network("104.24.0.0/14"),
    ipaddress.ip_network("172.64.0.0/13"),
    ipaddress.ip_network("131.0.72.0/22"),
    # IPv6
    ipaddress.ip_network("2400:cb00::/32"),
    ipaddress.ip_network("2606:4700::/32"),
    ipaddress.ip_network("2803:f800::/32"),
    ipaddress.ip_network("2405:b500::/32"),
    ipaddress.ip_network("2405:8100::/32"),
    ipaddress.ip_network("2a06:98c0::/29"),
    ipaddress.ip_network("2c0f:f248::/32"),
]


# Custom IPs to ignore (can be extended via environment)
@lru_cache(maxsize=1)
def get_ignored_ips() -> frozenset:
    """Get set of manually ignored IPs from environment."""
    env_ips = os.getenv("IGNORED_IPS", "")
    ips = frozenset(ip.strip() for ip in env_ips.split(",") if ip.strip())
    return ips


# Singleton instances
db_config = DatabaseConfig()
app_config = AppConfig()


def validate_config() -> list[str]:
    """Validate configuration and return list of errors."""
    errors = []
    
    # Database validation
    if not db_config.password:
        errors.append("DB_PASSWORD is required but not set")
    if not db_config.host:
        errors.append("DB_HOST is required but not set")
    if db_config.port < 1 or db_config.port > 65535:
        errors.append(f"DB_PORT must be between 1 and 65535, got {db_config.port}")
    
    # Auth validation
    if app_config.enable_auth:
        if not app_config.auth_password:
            errors.append("AUTH_PASSWORD is required when ENABLE_AUTH is true")
        if len(app_config.auth_password) < 8:
            errors.append("AUTH_PASSWORD should be at least 8 characters")
    
    # Network validation
    for network in app_config.allowed_networks:
        network = network.strip()
        if network:
            try:
                ipaddress.ip_network(network)
            except ValueError:
                errors.append(f"Invalid network in ALLOWED_NETWORKS: {network}")
    
    # Numeric validation
    if app_config.retention_days < 1:
        errors.append(f"RETENTION_DAYS must be at least 1, got {app_config.retention_days}")
    if app_config.block_duration < 60:
        errors.append(f"BLOCK_DURATION should be at least 60 seconds, got {app_config.block_duration}")
    
    # Cloudflare validation
    if app_config.enable_cloudflare:
        if not app_config.cloudflare_api_token:
            errors.append("CLOUDFLARE_API_TOKEN ist erforderlich, wenn Cloudflare aktiviert ist")
        if not app_config.cloudflare_zone_id:
            errors.append("CLOUDFLARE_ZONE_ID ist erforderlich, wenn Cloudflare aktiviert ist")
    
    return errors


def validate_config_or_exit():
    """Validate configuration and exit if invalid."""
    errors = validate_config()
    if errors:
        print("Configuration errors:", file=__import__("sys").stderr)
        for error in errors:
            print(f"  - {error}", file=__import__("sys").stderr)
        __import__("sys").exit(1)
