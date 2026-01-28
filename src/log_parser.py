"""Log parsing module for NPM Monitor."""

import glob
import logging
import os
import re
import ipaddress
from datetime import datetime
from functools import lru_cache
from typing import List, Tuple, Optional, Iterator, Dict, Any

from .config import (
    app_config,
    PRIVATE_NETWORKS,
    CLOUDFLARE_NETWORKS,
    get_ignored_ips
)

logger = logging.getLogger(__name__)

# NPM access log pattern
LOG_PATTERN = re.compile(
    r'\[(?P<time_local>.+?)\]\s+-\s+(?P<status>\d{3})\s+(?P<upstream_status>\d{3}|-)\s+-\s+'
    r'(?P<method>\S+)\s+(?P<scheme>\S+)\s+(?P<host>\S+)\s+"(?P<path>[^"]*)"\s+'
    r'\[Client\s+(?P<client_ip>[^\]]+)\]\s+\[Length\s+(?P<length>[^\]]+)\]\s+'
    r'\[Gzip\s+(?P<gzip>[^\]]+)\]\s+\[Sent-to\s+(?P<sent_to>[^\]]+)\]\s+'
    r'"(?P<user_agent>[^"]*)"\s+"(?P<referer>[^"]*)"'
)

# GeoIP reader (optional)
_geoip_reader = None


def init_geoip() -> bool:
    """Initialize GeoIP database if enabled and available."""
    global _geoip_reader

    if not app_config.enable_geoip:
        return False

    try:
        import geoip2.database
        if os.path.exists(app_config.geoip_db_path):
            _geoip_reader = geoip2.database.Reader(app_config.geoip_db_path)
            logger.info("GeoIP database loaded successfully")
            return True
        else:
            logger.warning(f"GeoIP database not found at {app_config.geoip_db_path}")
    except ImportError:
        logger.warning("geoip2 module not installed, GeoIP disabled")
    except Exception as e:
        logger.error(f"Failed to load GeoIP database: {e}")

    return False


@lru_cache(maxsize=4096)
def get_geoip_info(ip: str) -> Tuple[Optional[str], Optional[str]]:
    """Get country code and city for an IP address."""
    if _geoip_reader is None:
        return None, None

    try:
        response = _geoip_reader.city(ip)
        country = response.country.iso_code
        city = response.city.name
        return country, city
    except Exception:
        return None, None


def is_ip_in_networks(ip_str: str, networks: List) -> bool:
    """Check if IP is in any of the given networks."""
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        return any(ip_obj in net for net in networks)
    except ValueError:
        return False


@lru_cache(maxsize=4096)
def should_ignore_ip(ip_str: str) -> bool:
    """Check if an IP should be ignored based on filtering rules."""
    ip_str = ip_str.strip()

    # Check manual ignore list
    if ip_str in get_ignored_ips():
        return True

    # Check private networks
    if is_ip_in_networks(ip_str, PRIVATE_NETWORKS):
        return True

    # Check Cloudflare networks
    if is_ip_in_networks(ip_str, CLOUDFLARE_NETWORKS):
        return True

    return False


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single log line and return extracted data."""
    match = LOG_PATTERN.match(line)
    if not match:
        return None

    data = match.groupdict()
    client_ip = data["client_ip"].strip()

    # Filter ignored IPs
    if should_ignore_ip(client_ip):
        return None

    # Parse timestamp
    try:
        dt = datetime.strptime(data["time_local"], "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None

    # Parse status code
    try:
        status = int(data["status"])
    except ValueError:
        return None

    # Parse response length
    try:
        length = int(data["length"]) if data["length"] != "-" else 0
    except ValueError:
        length = 0

    # Get GeoIP info
    country, city = get_geoip_info(client_ip)

    return {
        "time": dt,
        "host": data["host"],
        "method": data["method"],
        "path": data["path"],
        "status": status,
        "remote_addr": client_ip,
        "user_agent": data["user_agent"],
        "referer": data["referer"] if data["referer"] != "-" else None,
        "response_length": length,
        "country_code": country,
        "city": city,
    }


def read_log_file(file_path: str, limit: int) -> Iterator[str]:
    """Read last N lines from a log file efficiently."""
    try:
        with open(file_path, "rb") as f:
            # Seek to end
            f.seek(0, 2)
            file_size = f.tell()

            if file_size == 0:
                return

            # Read in chunks from the end
            lines = []
            chunk_size = 8192
            position = file_size

            while len(lines) < limit and position > 0:
                read_size = min(chunk_size, position)
                position -= read_size
                f.seek(position)
                chunk = f.read(read_size).decode("utf-8", errors="ignore")

                # Handle partial lines
                if position > 0:
                    # Find first newline and discard partial line
                    newline_pos = chunk.find("\n")
                    if newline_pos != -1:
                        chunk = chunk[newline_pos + 1:]

                chunk_lines = chunk.splitlines()
                lines = chunk_lines + lines

            # Return only the last 'limit' lines
            for line in lines[-limit:]:
                if line.strip():
                    yield line

    except (FileNotFoundError, PermissionError) as e:
        logger.warning(f"Cannot read log file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error reading log file {file_path}: {e}")


def get_log_files() -> List[str]:
    """Get list of NPM access log files."""
    pattern = os.path.join(app_config.log_dir, "proxy-host-*_access.log")
    return glob.glob(pattern)


def parse_all_logs(limit_per_file: Optional[int] = None) -> List[Tuple]:
    """Parse all log files and return data ready for database insertion."""
    limit = limit_per_file or app_config.lines_per_file
    rows = []

    log_files = get_log_files()
    logger.info(f"Found {len(log_files)} log files to process")

    for file_path in log_files:
        file_rows = 0
        for line in read_log_file(file_path, limit):
            parsed = parse_log_line(line)
            if parsed:
                rows.append((
                    parsed["time"],
                    parsed["host"],
                    parsed["method"],
                    parsed["path"],
                    parsed["status"],
                    parsed["remote_addr"],
                    parsed["user_agent"],
                    parsed["referer"],
                    parsed["response_length"],
                    parsed["country_code"],
                    parsed["city"],
                ))
                file_rows += 1

        logger.debug(f"Parsed {file_rows} valid entries from {os.path.basename(file_path)}")

    logger.info(f"Total parsed entries: {len(rows)}")
    return rows
