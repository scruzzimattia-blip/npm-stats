"""Utility to sync and fetch hosts from Nginx Proxy Manager database."""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from ..config import app_config

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
            for row in result:
                # domain_names is usually a JSON-like string in NPM
                # We'll just clean it up a bit
                domains = row[0].replace('[', '').replace(']', '').replace('"', '').split(',')
                hosts.append({
                    "domains": [d.strip() for p in domains for d in p.split(',') if d.strip()],
                    "forward": f"{row[1]}:{row[2]}",
                    "enabled": bool(row[3]),
                    "ssl": bool(row[4]),
                })
        return hosts
    except Exception as e:
        logger.error(f"Failed to fetch hosts from NPM database: {e}")
        return []
