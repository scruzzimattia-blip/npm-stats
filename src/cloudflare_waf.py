"""Cloudflare WAF integration for IP blocking."""

import logging
from typing import Any, Dict, Optional

import requests

from .config import app_config

logger = logging.getLogger(__name__)


class CloudflareManager:
    """Manage Cloudflare Firewall Access Rules for IP blocking."""

    def __init__(self, api_token: str, zone_id: str):
        self.api_token = api_token
        self.zone_id = zone_id
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make a request to the Cloudflare API."""
        url = f"{self.base_url}/zones/{self.zone_id}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, json=data, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Cloudflare API error ({method} {endpoint}): {e}")
            if hasattr(e.response, "text"):
                logger.error(f"Response: {e.response.text}")
            return None

    def block_ip(self, ip: str, reason: str = "") -> bool:
        """
        Block an IP address in Cloudflare using a Firewall Access Rule.

        Args:
            ip: The IP address to block.
            reason: The reason for blocking (stored in notes).

        Returns:
            True if successful, False otherwise.
        """
        if not self.api_token or not self.zone_id:
            logger.error("Cloudflare API token or Zone ID not configured")
            return False

        # Check if already blocked to avoid duplicates
        existing_rule = self._find_rule(ip)
        if existing_rule:
            logger.debug(f"IP {ip} is already blocked on Cloudflare (Rule ID: {existing_rule['id']})")
            return True

        data = {
            "mode": "block",
            "configuration": {"target": "ip", "value": ip},
            "notes": f"npm-monitor-block: {reason}"[:255],
        }

        result = self._make_request("POST", "firewall/access_rules/rules", data=data)
        if result and result.get("success"):
            logger.info(f"Blocked IP {ip} on Cloudflare: {reason}")
            return True
        return False

    def unblock_ip(self, ip: str) -> bool:
        """
        Remove a Cloudflare Firewall Access Rule for an IP address.

        Args:
            ip: The IP address to unblock.

        Returns:
            True if successful, False otherwise.
        """
        rule = self._find_rule(ip)
        if not rule:
            logger.info(f"IP {ip} not found in Cloudflare access rules")
            return True

        rule_id = rule["id"]
        result = self._make_request("DELETE", f"firewall/access_rules/rules/{rule_id}")
        if result and result.get("success"):
            logger.info(f"Unblocked IP {ip} on Cloudflare")
            return True
        return False

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is currently blocked on Cloudflare."""
        return self._find_rule(ip) is not None

    def _find_rule(self, ip: str) -> Optional[Dict[str, Any]]:
        """Find an existing rule for the given IP."""
        params = {
            "notes": "npm-monitor-block",
            "configuration.target": "ip",
            "configuration.value": ip,
            "mode": "block",
            "match": "all",
        }

        result = self._make_request("GET", "firewall/access_rules/rules", params=params)
        if result and result.get("success") and result.get("result"):
            # Return the first matching rule
            return result["result"][0]
        return None


# Global manager instance
_cloudflare_manager: Optional[CloudflareManager] = None


def get_cloudflare_manager() -> Optional[CloudflareManager]:
    """Get or create global Cloudflare manager instance."""
    global _cloudflare_manager
    if _cloudflare_manager is None:
        if app_config.enable_cloudflare and app_config.cloudflare_api_token and app_config.cloudflare_zone_id:
            _cloudflare_manager = CloudflareManager(app_config.cloudflare_api_token, app_config.cloudflare_zone_id)
        else:
            return None
    return _cloudflare_manager
