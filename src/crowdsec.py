"""CrowdSec integration for IP reputation checks."""

import logging
from typing import Any, Dict, Optional

import requests

from .config import app_config

logger = logging.getLogger(__name__)

class CrowdSecManager:
    """Manage interaction with CrowdSec Local API (LAPI)."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "X-Api-Key": api_key,
            "User-Agent": "NPM-Monitor",
        }

    def get_ip_reputation(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        Check if an IP has any active decisions in CrowdSec.

        Returns:
            Dictionary with decision details or None if no decision found.
        """
        if not self.api_key:
            return None

        url = f"{self.api_url}/v1/decisions"
        params = {"ip": ip}

        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=5
            )
            response.raise_for_status()
            decisions = response.json()

            if decisions and isinstance(decisions, list):
                # Return the most relevant decision (usually there's only one active)
                return decisions[0]
            return None
        except Exception as e:
            logger.error(f"CrowdSec API error for IP {ip}: {e}")
            return None

    def is_ip_banned(self, ip: str) -> bool:
        """Check if an IP is currently banned by CrowdSec."""
        decision = self.get_ip_reputation(ip)
        return decision is not None

# Global manager instance
_crowdsec_manager: Optional[CrowdSecManager] = None

def get_crowdsec_manager() -> Optional[CrowdSecManager]:
    """Get or create global CrowdSec manager instance."""
    global _crowdsec_manager
    if _crowdsec_manager is None:
        if app_config.enable_crowdsec and app_config.crowdsec_api_key:
            _crowdsec_manager = CrowdSecManager(
                app_config.crowdsec_api_url,
                app_config.crowdsec_api_key
            )
        else:
            return None
    return _crowdsec_manager
