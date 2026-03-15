"""Utility to sync and fetch hosts from Nginx Proxy Manager database."""
import logging
import requests
import ssl
import socket
import time
import streamlit as st
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from ..config import app_config
from ..database import update_host_health

logger = logging.getLogger(__name__)

def get_npm_engine():
    """Create a SQLAlchemy engine for the NPM database."""
    if app_config.npm_db_type == "sqlite":
        return create_engine(f"sqlite:///{app_config.npm_db_sqlite_path}")
    else:
        # mysql
        return create_engine(
            f"mysql+pymysql://{app_config.npm_db_user}:{app_config.npm_db_password}@"
            f"{app_config.npm_db_host}:{app_config.npm_db_port}/{app_config.npm_db_name}"
        )

@st.cache_data(ttl=300)
def fetch_npm_proxy_hosts() -> List[Dict[str, Any]]:
    """Fetch proxy hosts and their SSL status from NPM database."""
    if not app_config.npm_db_password and app_config.npm_db_type == "mysql":
        logger.debug("NPM MySQL password not set, skipping fetch.")
        return []

    query = """
        SELECT 
            domain_names, 
            forward_host, 
            forward_port, 
            enabled, 
            ssl_forced,
            meta
        FROM proxy_host
        WHERE is_deleted = 0
    """
    
    hosts = []
    try:
        engine = get_npm_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.mappings().all()
            logger.info(f"NPM DB query returned {len(rows)} rows.")
            for row in rows:
                # domain_names is usually a JSON-like string in NPM, e.g. ["domain.com"]
                raw_domains = row["domain_names"]
                if isinstance(raw_domains, str):
                    # Remove JSON array characters and quotes
                    clean_domains = raw_domains.strip('[]"\'').split(',')
                    domains = [d.strip(' "\'') for d in clean_domains if d.strip(' "\'')]
                else:
                    domains = []
                
                if domains:
                    logger.debug(f"Found host: {domains[0]} forwarding to {row['forward_host']}:{row['forward_port']}")

                hosts.append({
                    "domains": domains,
                    "forward": f"{row['forward_host']}:{row['forward_port']}",
                    "enabled": bool(row["enabled"]),
                    "ssl": bool(row["ssl_forced"]),
                })
        return hosts
    except Exception as e:
        logger.error(f"Failed to fetch hosts from NPM database: {e}")
        return []


def get_ssl_expiry(hostname: str) -> Optional[datetime]:
    """Get SSL certificate expiry date for a hostname."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                # 'Mar 12 12:00:00 2026 GMT'
                expiry_str = cert['notAfter']
                return datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc)
    except Exception:
        return None


def check_all_hosts_health():
    """Iterate through all NPM hosts and check their uptime and SSL."""
    hosts = fetch_npm_proxy_hosts()
    if not hosts:
        return

    for h in hosts:
        # Check primary domain
        if not h["domains"]:
            continue
        domain = h["domains"][0]

        start_time = time.time()
        is_up = False
        status_code = 0
        ssl_expiry = None

        try:
            # 1. HTTP/S Check (try https if ssl enabled, else http)
            url = f"https://{domain}" if h["ssl"] else f"http://{domain}"
            response = requests.get(url, timeout=10, allow_redirects=True, verify=False)
            status_code = response.status_code
            is_up = True if status_code < 500 else False

            # 2. SSL Check
            if h["ssl"]:
                ssl_expiry = get_ssl_expiry(domain)
        except Exception as e:
            logger.debug(f"Health check failed for {domain}: {e}")
            is_up = False

        response_time = round(time.time() - start_time, 3)

        # Update DB
        update_host_health(domain, is_up, status_code, ssl_expiry, response_time)

