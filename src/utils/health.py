"""Health check utility for Nginx Proxy Manager and system components."""

import logging
import os
import socket
import subprocess
from typing import Any, Dict

import streamlit as st

from ..database import get_newest_timestamp
from ..database import health_check as db_health_check
from ..firewall import get_iptables_manager

logger = logging.getLogger(__name__)


def get_npm_host() -> str:
    """Get the NPM host to check, defaults to host.docker.internal or localhost."""
    return os.getenv("NPM_HOST", "host.docker.internal")


@st.cache_data(ttl=60)
def check_npm_status(host: str = None, ports: tuple = (80, 81, 443)) -> Dict[int, bool]:
    """
    Check if the specified ports are open on the given host.

    Args:
        host: The hostname or IP to check.
        ports: Tuple of ports to check.

    Returns:
        Dictionary mapping port to a boolean indicating if it's open.
    """
    if host is None:
        host = get_npm_host()

    status = {}
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            # Try to connect
            result = sock.connect_ex((host, port))
            status[port] = result == 0
        except Exception as e:
            logger.debug(f"Health check failed for {host}:{port} - {e}")
            status[port] = False
        finally:
            sock.close()

    # Fallback to localhost if host.docker.internal fails completely and it was the default
    if host == "host.docker.internal" and not any(status.values()):
        return check_npm_status("localhost", ports)

    return status


def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health status."""
    health = {
        "database": db_health_check(),
        "redis": False,
        "log_worker": False,
        "firewall": {
            "available": False,
            "has_permissions": False,
            "rules_count": 0,
            "parent_chain": "UNKNOWN"
        },
        "last_data": None
    }

    # 1. Redis Check
    try:
        from ..database import get_redis
        r = get_redis()
        health["redis"] = r.ping()
    except Exception:
        pass

    # 2. Log Worker Check (via Process check or Redis heartbeat)
    # For now, we'll check if the process is running using a simple heuristic
    try:
        # Check if process with log_worker.py is running
        cmd = ["pgrep", "-f", "log_worker.py"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        health["log_worker"] = result.returncode == 0
    except Exception:
        pass

    # 3. Firewall Check
    manager = get_iptables_manager()
    health["firewall"]["available"] = manager.available
    health["firewall"]["has_permissions"] = manager.has_permissions or manager.use_sudo
    health["firewall"]["parent_chain"] = getattr(manager, "parent_chain", "INPUT")
    if health["firewall"]["has_permissions"]:
        health["firewall"]["rules_count"] = len(manager.list_blocked_ips())

    # 4. Last Data Timestamp
    health["last_data"] = get_newest_timestamp()

    return health

