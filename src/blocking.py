"""IP blocking module for automatic threat detection and blocking."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from .config import app_config

logger = logging.getLogger(__name__)


class IPBlocker:
    """Automatic IP blocking based on attack patterns."""

    def __init__(self, use_firewall: bool = False):
        self.request_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {
                "404": 0,
                "403": 0,
                "5xx": 0,
                "suspicious": 0,
                "total_failed": 0,
            }
        )
        self.request_timestamps: Dict[str, List[datetime]] = defaultdict(list)
        self.blocked_ips: Dict[str, datetime] = {}  # IP -> block_until
        self.whitelisted_ips: Set[str] = set()
        self.use_firewall = use_firewall

        # Initialize firewall manager if enabled
        self._iptables = None
        if use_firewall:
            try:
                from .firewall import get_iptables_manager

                self._iptables = get_iptables_manager()
                if self._iptables.has_permissions:
                    logger.info("Firewall-level blocking enabled (iptables)")
                    # Create chain for NPM Monitor rules
                    self._iptables.create_chain()
                else:
                    logger.warning("Firewall permissions not available, using application-level blocking only")
                    self.use_firewall = False
            except Exception as e:
                logger.error(f"Failed to initialize iptables: {e}")
                self.use_firewall = False

    def check_request(
        self, ip: str, status: int, path: str, host: str = ""
    ) -> Optional[str]:
        """
        Check if a request should trigger blocking.

        Args:
            ip: Client IP address
            status: HTTP status code
            path: Request path
            host: Request host

        Returns:
            Block reason if IP should be blocked, None otherwise
        """
        if not app_config.enable_blocking:
            return None

        if ip in self.whitelisted_ips:
            return None

        now = datetime.now()
        reason = None

        # Clean old timestamps (keep last 5 minutes)
        self._cleanup_old_timestamps(ip, now)

        # Track request timestamp
        self.request_timestamps[ip].append(now)

        # Update counters based on status
        if status == 404:
            self.request_counts[ip]["404"] += 1
            self.request_counts[ip]["total_failed"] += 1
        elif status == 403:
            self.request_counts[ip]["403"] += 1
            self.request_counts[ip]["total_failed"] += 1
        elif status >= 500:
            self.request_counts[ip]["5xx"] += 1
            self.request_counts[ip]["total_failed"] += 1

        # Check suspicious paths
        if self._is_suspicious_path(path):
            self.request_counts[ip]["suspicious"] += 1
            self.request_counts[ip]["total_failed"] += 1

        # Check thresholds
        reason = self._check_thresholds(ip)

        if reason:
            self._block_ip(ip, reason)
            logger.warning(f"Blocking IP {ip}: {reason}")

        return reason

    def _check_thresholds(self, ip: str) -> Optional[str]:
        """Check if IP exceeds any threshold."""
        counts = self.request_counts[ip]

        if counts["404"] >= app_config.max_404_errors:
            return f"Too many 404 errors ({counts['404']}/{app_config.max_404_errors})"

        if counts["403"] >= app_config.max_403_errors:
            return f"Too many 403 errors ({counts['403']}/{app_config.max_403_errors})"

        if counts["5xx"] >= app_config.max_5xx_errors:
            return f"Too many 5xx errors ({counts['5xx']}/{app_config.max_5xx_errors})"

        if counts["total_failed"] >= app_config.max_failed_requests:
            return f"Too many failed requests ({counts['total_failed']}/{app_config.max_failed_requests})"

        if counts["suspicious"] >= app_config.max_suspicious_paths:
            return f"Suspicious activity detected ({counts['suspicious']}/{app_config.max_suspicious_paths} suspicious paths)"

        return None

    def _is_suspicious_path(self, path: str) -> bool:
        """Check if path is suspicious."""
        path_lower = path.lower()
        for suspicious in app_config.suspicious_paths:
            if suspicious.lower() in path_lower:
                return True
        return False

    def _cleanup_old_timestamps(self, ip: str, now: datetime):
        """Remove timestamps older than 5 minutes."""
        cutoff = now - timedelta(minutes=5)
        self.request_timestamps[ip] = [
            ts for ts in self.request_timestamps[ip] if ts > cutoff
        ]

        # Also reset counts if no recent requests
        if not self.request_timestamps[ip]:
            self.request_counts[ip] = {
                "404": 0,
                "403": 0,
                "5xx": 0,
                "suspicious": 0,
                "total_failed": 0,
            }

    def _block_ip(self, ip: str, reason: str):
        """Block an IP address."""
        block_until = datetime.now() + timedelta(seconds=app_config.block_duration)
        self.blocked_ips[ip] = block_until

        # Block at firewall level if enabled
        if self.use_firewall and self._iptables:
            try:
                self._iptables.block_ip(ip, reason)
            except Exception as e:
                logger.error(f"Failed to block IP {ip} at firewall level: {e}")

        # Reset counters after blocking
        self.request_counts[ip] = {
            "404": 0,
            "403": 0,
            "5xx": 0,
            "suspicious": 0,
            "total_failed": 0,
        }
        self.request_timestamps[ip] = []

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is currently blocked."""
        if ip in self.whitelisted_ips:
            return False

        # Check application-level block
        if ip in self.blocked_ips:
            # Check if block has expired
            if datetime.now() > self.blocked_ips[ip]:
                del self.blocked_ips[ip]
                return False
            return True

        # Check firewall-level block if enabled
        if self.use_firewall and self._iptables:
            return self._iptables.is_blocked(ip)

        return False

    def get_block_reason(self, ip: str) -> Optional[str]:
        """Get the reason why an IP is blocked."""
        if not self.is_blocked(ip):
            return None

        return f"Blocked until {self.blocked_ips[ip].strftime('%Y-%m-%d %H:%M:%S')}"

    def unblock_ip(self, ip: str) -> bool:
        """Manually unblock an IP."""
        unblocked = False

        # Unblock from application-level
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
            unblocked = True

        # Unblock from firewall level
        if self.use_firewall and self._iptables:
            try:
                self._iptables.unblock_ip(ip)
                unblocked = True
            except Exception as e:
                logger.error(f"Failed to unblock IP {ip} at firewall level: {e}")

        if unblocked:
            logger.info(f"IP {ip} has been unblocked")

        return unblocked

    def whitelist_ip(self, ip: str):
        """Add IP to whitelist (never block)."""
        self.whitelisted_ips.add(ip)
        # Remove from blocked if present
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
        logger.info(f"IP {ip} added to whitelist")

    def remove_from_whitelist(self, ip: str):
        """Remove IP from whitelist."""
        self.whitelisted_ips.discard(ip)
        logger.info(f"IP {ip} removed from whitelist")

    def get_blocked_ips(self) -> Dict[str, datetime]:
        """Get all currently blocked IPs."""
        # Clean expired blocks
        now = datetime.now()
        expired = [ip for ip, until in self.blocked_ips.items() if now > until]
        for ip in expired:
            del self.blocked_ips[ip]

        return dict(self.blocked_ips)

    def get_stats(self) -> Dict:
        """Get blocking statistics."""
        return {
            "total_blocked": len(self.get_blocked_ips()),
            "whitelisted": len(self.whitelisted_ips),
            "tracked_ips": len(self.request_counts),
        }

    def cleanup_old_ips(self, max_age_minutes: int = 60):
        """Remove old IPs from memory to prevent memory leaks.
        
        Args:
            max_age_minutes: Maximum age of IP tracking data in minutes
        """
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        
        # Find IPs with no recent activity
        ips_to_remove = []
        for ip, timestamps in self.request_timestamps.items():
            # Keep IPs that are currently blocked
            if ip in self.blocked_ips:
                continue
            # Keep whitelisted IPs
            if ip in self.whitelisted_ips:
                continue
            # Remove IPs with no recent timestamps
            if not timestamps or all(ts < cutoff for ts in timestamps):
                ips_to_remove.append(ip)
        
        # Remove old IPs
        for ip in ips_to_remove:
            del self.request_timestamps[ip]
            del self.request_counts[ip]
        
        if ips_to_remove:
            logger.debug(f"Cleaned up {len(ips_to_remove)} old IPs from memory")


# Global blocker instance
_blocker: Optional[IPBlocker] = None


def get_blocker(use_firewall: bool = False) -> IPBlocker:
    """Get or create the global blocker instance.
    
    Args:
        use_firewall: Enable firewall-level blocking with iptables
    """
    global _blocker
    if _blocker is None:
        _blocker = IPBlocker(use_firewall=use_firewall)
    return _blocker