"""Utility to fetch information about local Docker containers."""

import logging
import os
from typing import List, Dict, Any

try:
    import docker
except ImportError:
    docker = None

logger = logging.getLogger(__name__)

def get_container_status() -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Fetch status and basic stats for relevant containers. Returns (data, error_message)."""
    if docker is None:
        return [], "Python-Bibliothek 'docker' ist nicht installiert. Bitte uv.lock aktualisieren."

    try:
        # Check if socket exists
        socket_path = "/var/run/docker.sock"
        if not os.path.exists(socket_path):
            return [], f"Docker-Socket nicht gefunden unter {socket_path}. Ist der Mount im docker-compose korrekt?"
            
        # Connect via explicit unix socket path
        client = docker.DockerClient(base_url=f"unix://{socket_path}")
        # Test connection
        client.ping()
    except Exception as e:
        return [], f"Verbindung zum Docker-Socket fehlgeschlagen: {e}. Läuft der Container als root?"

    containers_info = []
    try:
        # List all containers
        containers = client.containers.list(all=True)
        
        for c in containers:
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
                
        return sorted(containers_info, key=lambda x: x['name']), None
    except Exception as e:
        logger.error(f"Error fetching Docker containers: {e}")
        return [], str(e)
