"""Health check utility for Nginx Proxy Manager."""

import socket
import logging
import os
import streamlit as st
from typing import Dict

logger = logging.getLogger(__name__)

def get_npm_host() -> str:
    """Get the NPM host to check, defaults to host.docker.internal or localhost."""
    return os.getenv("NPM_HOST", "host.docker.internal")

@st.cache_data(ttl=60)
def check_npm_status(host: str = None, ports: tuple = (80, 81, 443)) -> Dict[int, bool]:
    """
    Check if the specified ports are open on the given host.
...
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
            status[port] = (result == 0)
        except Exception as e:
            logger.debug(f"Health check failed for {host}:{port} - {e}")
            status[port] = False
        finally:
            sock.close()
            
    # Fallback to localhost if host.docker.internal fails completely and it was the default
    if host == "host.docker.internal" and not any(status.values()):
        return check_npm_status("localhost", ports)
            
    return status
