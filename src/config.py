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
    enable_auth: bool = field(default_factory=lambda: os.getenv("ENABLE_AUTH", "false").lower() == "true")
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
    max_suspicious_paths: int = field(default_factory=lambda: int(os.getenv("MAX_SUSPICIOUS_PATHS", "5")))
    use_firewall: bool = field(default_factory=lambda: os.getenv("USE_FIREWALL", "false").lower() == "true")


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
    
    return errors


def validate_config_or_exit():
    """Validate configuration and exit if invalid."""
    errors = validate_config()
    if errors:
        print("Configuration errors:", file=__import__("sys").stderr)
        for error in errors:
            print(f"  - {error}", file=__import__("sys").stderr)
        __import__("sys").exit(1)
