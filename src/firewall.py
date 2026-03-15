"""Firewall integration for IP blocking using iptables."""

import logging
import subprocess
from typing import List, Optional

from .config import app_config

logger = logging.getLogger(__name__)


class IptablesManager:
    """Manage iptables rules for IP blocking."""

    CHAIN_NAME = "NPM_MONITOR"
    COMMENT_PREFIX = "npm-monitor"

    def __init__(self):
        self.available = self._check_iptables_available()
        self.has_permissions = self._check_permissions()
        self.use_sudo = not self.has_permissions

        # Determine parent chain (INPUT or DOCKER-USER)
        if app_config.iptables_parent_chain:
            self.parent_chain = app_config.iptables_parent_chain
        elif app_config.use_docker:
            self.parent_chain = "DOCKER-USER"
        else:
            self.parent_chain = "INPUT"

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
            # Try to list rules
            result = subprocess.run(
                ["iptables", "-L", "-n"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def create_chain(self) -> bool:
        """Create custom chain for NPM Monitor rules."""
        if not self.has_permissions and not self.use_sudo:
            logger.error("No permissions to create iptables chain")
            return False

        try:
            # Create chain if it doesn't exist
            self._run_iptables(["-N", self.CHAIN_NAME])

            # Add chain to parent (only once)
            # Check if it already exists in parent
            result = self._run_iptables(["-C", self.parent_chain, "-j", self.CHAIN_NAME])

            if result.returncode != 0:
                # Add to top of parent chain
                self._run_iptables(["-I", self.parent_chain, "1", "-j", self.CHAIN_NAME])

            logger.info(f"Initialized iptables chain {self.CHAIN_NAME} in {self.parent_chain}")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to create iptables chain: {e}")
            return False

    def block_ip(self, ip: str, reason: str = "") -> bool:
        """Block an IP address using iptables DROP rule."""
        if not self.has_permissions and not self.use_sudo:
            return False

        # Check if already blocked
        if self.is_blocked(ip):
            return True

        try:
            comment = f"{self.COMMENT_PREFIX}: {reason}"[:255] if reason else self.COMMENT_PREFIX

            self._run_iptables([
                "-A", self.CHAIN_NAME,
                "-s", ip,
                "-j", "DROP",
                "-m", "comment",
                "--comment", comment
            ])

            logger.info(f"Blocked IP {ip} at firewall level ({self.parent_chain}): {reason}")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to block IP {ip}: {e}")
            return False

    def unblock_ip(self, ip: str) -> bool:
        """Remove iptables block for an IP address."""
        if not self.has_permissions and not self.use_sudo:
            return False

        try:
            # Delete all rules for this IP in our chain
            self._run_iptables(["-D", self.CHAIN_NAME, "-s", ip, "-j", "DROP"])
            logger.info(f"Unblocked IP {ip} at firewall level")
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to unblock IP {ip}: {e}")
            return False

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is blocked in iptables."""
        if not self.has_permissions and not self.use_sudo:
            return False

        try:
            result = self._run_iptables(["-C", self.CHAIN_NAME, "-s", ip, "-j", "DROP"])
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False

    def list_blocked_ips(self) -> List[str]:
        """List all IPs blocked by NPM Monitor."""
        if not self.has_permissions and not self.use_sudo:
            return []

        try:
            result = self._run_iptables(["-L", self.CHAIN_NAME, "-n"])

            if result.returncode != 0:
                return []

            blocked_ips = []
            for line in result.stdout.split("\n"):
                if "DROP" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        # Extract IP
                        ip = parts[3]
                        if "/" in ip:
                            ip = ip.split("/")[0]
                        blocked_ips.append(ip)

            return blocked_ips

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to list blocked IPs: {e}")
            return []

    def flush_chain(self) -> bool:
        """Remove all rules from NPM Monitor chain."""
        if not self.has_permissions and not self.use_sudo:
            return False

        try:
            self._run_iptables(["-F", self.CHAIN_NAME])
            logger.info(f"Flushed all rules from chain {self.CHAIN_NAME}")
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to flush chain: {e}")
            return False

    def delete_chain(self) -> bool:
        """Delete NPM Monitor chain completely."""
        if not self.has_permissions and not self.use_sudo:
            return False

        try:
            self.flush_chain()
            self._run_iptables(["-D", self.parent_chain, "-j", self.CHAIN_NAME])
            self._run_iptables(["-X", self.CHAIN_NAME])
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
