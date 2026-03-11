"""Configuration module for NPM Monitor."""

import ipaddress
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List
from urllib.parse import quote_plus


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "npm-monitor-db"))
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

    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "/logs"))
    lines_per_file: int = field(default_factory=lambda: int(os.getenv("LINES_PER_FILE", "10000")))
    max_display_rows: int = field(default_factory=lambda: int(os.getenv("MAX_DISPLAY_ROWS", "50000")))
    retention_days: int = field(default_factory=lambda: int(os.getenv("RETENTION_DAYS", "30")))
    enable_geoip: bool = field(default_factory=lambda: os.getenv("ENABLE_GEOIP", "false").lower() == "true")
    geoip_db_path: str = field(default_factory=lambda: os.getenv("GEOIP_DB_PATH", "/geoip/GeoLite2-City.mmdb"))
    enable_auth: bool = field(default_factory=lambda: os.getenv("ENABLE_AUTH", "true").lower() == "true")
    auth_username: str = field(default_factory=lambda: os.getenv("AUTH_USERNAME", "admin"))
    auth_password: str = field(default_factory=lambda: os.getenv("AUTH_PASSWORD", ""))
    allowed_networks: List[str] = field(default_factory=lambda: os.getenv("ALLOWED_NETWORKS", "127.0.0.1/32").split(","))
    # Blocking configuration
    enable_blocking: bool = field(default_factory=lambda: os.getenv("ENABLE_BLOCKING", "true").lower() == "true")
    block_duration: int = field(default_factory=lambda: int(os.getenv("BLOCK_DURATION", "3600")))  # 1 hour
    max_404_errors: int = field(default_factory=lambda: int(os.getenv("MAX_404_ERRORS", "20")))  # per 5 minutes
    max_403_errors: int = field(default_factory=lambda: int(os.getenv("MAX_403_ERRORS", "10")))  # per 5 minutes
    max_5xx_errors: int = field(default_factory=lambda: int(os.getenv("MAX_5XX_ERRORS", "50")))  # per 5 minutes
    max_failed_requests: int = field(default_factory=lambda: int(os.getenv("MAX_FAILED_REQUESTS", "100")))  # per 5 minutes
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
