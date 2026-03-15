"""Utility to fetch information about local Docker containers."""

import logging
import os
from typing import List, Dict, Any

try:
    import docker
except ImportError:
    docker = None

logger = logging.getLogger(__name__)

def get_docker_client():
    """Create a Docker client if available."""
    if docker is None:
        return None
    
    try:
        # Connect via default socket
        return docker.from_env()
    except Exception as e:
        logger.debug(f"Docker connection failed: {e}")
        return None

def get_container_status() -> List[Dict[str, Any]]:
    """Fetch status and basic stats for relevant containers."""
    client = get_docker_client()
    if not client:
        return []

    containers_info = []
    try:
        # List all containers (or filter if needed)
        containers = client.containers.list(all=True)
        
        for c in containers:
            # We focus on NPM related or all active containers
            # Get stats (non-blocking)
            try:
                # Basic info
                info = {
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                    "uptime": c.attrs.get('State', {}).get('StartedAt', ''),
                }
                
                # Check health if available
                health = c.attrs.get('State', {}).get('Health', {}).get('Status', 'N/A')
                info["health"] = health
                
                containers_info.append(info)
            except Exception:
                continue
                
        return sorted(containers_info, key=lambda x: x['name'])
    except Exception as e:
        logger.error(f"Error fetching Docker containers: {e}")
        return []
