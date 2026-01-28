"""Utility functions for NPM Monitor."""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def format_number(n: int) -> str:
    """Format a number with thousand separators."""
    return f"{n:,}"


def format_bytes(size: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def calculate_error_rate(total: int, errors: int) -> float:
    """Calculate error rate as percentage."""
    if total == 0:
        return 0.0
    return (errors / total) * 100


def get_time_ranges() -> dict:
    """Get predefined time range options."""
    now = datetime.now()
    return {
        "Letzte Stunde": (now - timedelta(hours=1), now),
        "Letzte 6 Stunden": (now - timedelta(hours=6), now),
        "Letzte 24 Stunden": (now - timedelta(hours=24), now),
        "Letzte 7 Tage": (now - timedelta(days=7), now),
        "Letzte 30 Tage": (now - timedelta(days=30), now),
        "Alles": (None, None),
    }


def parse_user_agent(ua: str) -> dict:
    """Parse user agent string into components."""
    ua_lower = ua.lower() if ua else ""

    # Detect browser
    browser = "Unbekannt"
    if "firefox" in ua_lower:
        browser = "Firefox"
    elif "edg" in ua_lower:
        browser = "Edge"
    elif "chrome" in ua_lower:
        browser = "Chrome"
    elif "safari" in ua_lower:
        browser = "Safari"
    elif "opera" in ua_lower or "opr" in ua_lower:
        browser = "Opera"

    # Detect OS
    os_name = "Unbekannt"
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac os" in ua_lower or "macos" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"

    # Detect device type
    device = "Desktop"
    if "mobile" in ua_lower or "android" in ua_lower:
        device = "Mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device = "Tablet"
    elif "bot" in ua_lower or "crawler" in ua_lower or "spider" in ua_lower:
        device = "Bot"

    return {
        "browser": browser,
        "os": os_name,
        "device": device,
    }


def get_status_category(status: int) -> str:
    """Categorize HTTP status code."""
    if status < 200:
        return "1xx Informational"
    elif status < 300:
        return "2xx Success"
    elif status < 400:
        return "3xx Redirect"
    elif status < 500:
        return "4xx Client Error"
    else:
        return "5xx Server Error"


def df_to_csv(df: pd.DataFrame) -> str:
    """Convert DataFrame to CSV string."""
    return df.to_csv(index=False)


def get_relative_time(dt: datetime) -> str:
    """Get human-readable relative time."""
    if dt is None:
        return "Nie"

    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt

    if diff.total_seconds() < 60:
        return "Gerade eben"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"vor {minutes} Min."
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"vor {hours} Std."
    else:
        days = int(diff.total_seconds() / 86400)
        return f"vor {days} Tagen"
