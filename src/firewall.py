"""Firewall integration for IP blocking using iptables."""

import logging
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


class IptablesManager:
    """Manage iptables rules for IP blocking."""

    CHAIN_NAME = "NPM_MONITOR"
    COMMENT_PREFIX = "npm-monitor"

    def __init__(self):
        self.available = self._check_iptables_available()
        self.has_permissions = self._check_permissions()
        self.use_sudo = not self.has_permissions

    def _run_iptables(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run iptables command with optional sudo."""
        cmd = ["sudo", "iptables"] + args if self.use_sudo else ["iptables"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5)

    def _check_iptables_available(self) -> bool:
        """Check if iptables is available on the system."""
        try:
            result = self._run_iptables(["--version"])
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("iptables not available on this system")
            return False

    def _check_permissions(self) -> bool:
        """Check if we have permissions to modify iptables."""
        if not self.available:
            return False

        try:
            # Try to list rules (requires NET_ADMIN capability)
            result = self._run_iptables(["-L", self.CHAIN_NAME, "-n"])
            # If chain doesn't exist, we'll get an error, but that's ok
            # We have permissions if we can run iptables at all
            return True
        except subprocess.SubprocessError as e:
            logger.warning(f"No permissions to manage iptables: {e}")
            return False
            # If chain doesn't exist, we'll get an error, but that's ok
            # We have permissions if we can run iptables at all
            return True
        except subprocess.SubprocessError as e:
            logger.warning(f"No permissions to manage iptables: {e}")
            return False

    def create_chain(self) -> bool:
        """Create custom chain for NPM Monitor rules."""
        if not self.has_permissions:
            logger.error("No permissions to create iptables chain")
            return False

        try:
            # Create chain
            subprocess.run(
                ["iptables", "-N", self.CHAIN_NAME],
                capture_output=True,
                check=False,
                timeout=5,
            )

            # Add chain to INPUT (only once)
            result = subprocess.run(
                ["iptables", "-C", "INPUT", "-j", self.CHAIN_NAME],
                capture_output=True,
                timeout=5,
            )

            if result.returncode != 0:
                subprocess.run(
                    ["iptables", "-I", "INPUT", "1", "-j", self.CHAIN_NAME],
                    capture_output=True,
                    check=True,
                    timeout=5,
                )

            logger.info(f"Created iptables chain: {self.CHAIN_NAME}")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to create iptables chain: {e}")
            return False

    def block_ip(self, ip: str, reason: str = "") -> bool:
        """Block an IP address using iptables DROP rule."""
        if not self.has_permissions:
            logger.error(f"No permissions to block IP {ip}")
            return False

        # Check if already blocked
        if self.is_blocked(ip):
            logger.debug(f"IP {ip} is already blocked")
            return True

        try:
            comment = f"{self.COMMENT_PREFIX}: {reason}"[:255] if reason else self.COMMENT_PREFIX

            subprocess.run(
                ["iptables", "-A", self.CHAIN_NAME, "-s", ip, "-j", "DROP", "-m", "comment", "--comment", comment],
                capture_output=True,
                check=True,
                timeout=5,
            )

            logger.info(f"Blocked IP {ip} at firewall level: {reason}")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to block IP {ip}: {e}")
            return False

    def unblock_ip(self, ip: str) -> bool:
        """Remove iptables block for an IP address."""
        if not self.has_permissions:
            logger.error(f"No permissions to unblock IP {ip}")
            return False

        try:
            # Delete all rules for this IP
            subprocess.run(
                ["iptables", "-D", self.CHAIN_NAME, "-s", ip, "-j", "DROP"],
                capture_output=True,
                timeout=5,
            )

            logger.info(f"Unblocked IP {ip} at firewall level")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to unblock IP {ip}: {e}")
            return False

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is blocked in iptables."""
        if not self.has_permissions:
            return False

        try:
            result = subprocess.run(
                ["iptables", "-C", self.CHAIN_NAME, "-s", ip, "-j", "DROP"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0

        except subprocess.SubprocessError:
            return False

    def list_blocked_ips(self) -> List[str]:
        """List all IPs blocked by NPM Monitor."""
        if not self.has_permissions:
            return []

        try:
            result = subprocess.run(
                ["iptables", "-L", self.CHAIN_NAME, "-n"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return []

            blocked_ips = []
            for line in result.stdout.split("\n"):
                if "DROP" in line and self.COMMENT_PREFIX in line:
                    # Extract IP from line like: "DROP       all  --  192.168.1.100  anywhere"
                    parts = line.split()
                    if len(parts) >= 4:
                        blocked_ips.append(parts[3])

            return blocked_ips

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to list blocked IPs: {e}")
            return []

    def flush_chain(self) -> bool:
        """Remove all rules from NPM Monitor chain."""
        if not self.has_permissions:
            logger.error("No permissions to flush iptables chain")
            return False

        try:
            subprocess.run(
                ["iptables", "-F", self.CHAIN_NAME],
                capture_output=True,
                check=True,
                timeout=5,
            )

            logger.info(f"Flushed all rules from chain {self.CHAIN_NAME}")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to flush chain: {e}")
            return False

    def delete_chain(self) -> bool:
        """Delete NPM Monitor chain completely."""
        if not self.has_permissions:
            logger.error("No permissions to delete iptables chain")
            return False

        try:
            # Flush first
            self.flush_chain()

            # Remove chain from INPUT
            subprocess.run(
                ["iptables", "-D", "INPUT", "-j", self.CHAIN_NAME],
                capture_output=True,
                timeout=5,
            )

            # Delete chain
            subprocess.run(
                ["iptables", "-X", self.CHAIN_NAME],
                capture_output=True,
                check=True,
                timeout=5,
            )

            logger.info(f"Deleted iptables chain {self.CHAIN_NAME}")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to delete chain: {e}")
            return False


# Global iptables manager instance
_iptables_manager: Optional[IptablesManager] = None


def get_iptables_manager() -> IptablesManager:
    """Get or create global iptables manager instance."""
    global _iptables_manager
    if _iptables_manager is None:
        _iptables_manager = IptablesManager()
    return _iptables_manager