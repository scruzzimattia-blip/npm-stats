"""IP blocking module for automatic threat detection and blocking."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from .config import app_config
from .database import (
    update_request_counters,
    reset_request_counters,
    cleanup_old_trackers,
    get_tracked_ip_count,
    get_whitelist
)
from .notifications import send_notification

logger = logging.getLogger(__name__)


class IPBlocker:
    """Automatic IP blocking based on attack patterns with shared state in DB."""

    def __init__(self, use_firewall: bool = False):
        self.blocked_ips: Dict[str, datetime] = {}  # IP -> block_until (local cache)
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
                    self._iptables.create_chain()
                else:
                    logger.warning("Firewall permissions not available, using application-level blocking only")
                    self.use_firewall = False
            except Exception as e:
                logger.error(f"Failed to initialize iptables: {e}")
                self.use_firewall = False

        # Initialize Cloudflare manager if enabled
        self._cloudflare = None
        if app_config.enable_cloudflare:
            try:
                from .cloudflare_waf import get_cloudflare_manager
                self._cloudflare = get_cloudflare_manager()
                if self._cloudflare:
                    logger.info("Cloudflare-level blocking enabled")
                else:
                    logger.warning("Cloudflare enabled but manager could not be initialized (check API credentials)")
            except Exception as e:
                logger.error(f"Failed to initialize Cloudflare: {e}")

        # Initialize CrowdSec manager if enabled
        self._crowdsec = None
        if app_config.enable_crowdsec:
            try:
                from .crowdsec import get_crowdsec_manager
                self._crowdsec = get_crowdsec_manager()
                if self._crowdsec:
                    logger.info("CrowdSec reputation checks enabled")
            except Exception as e:
                logger.error(f"Failed to initialize CrowdSec: {e}")

    def check_request(
        self, ip: str, status: int, path: str, host: str = ""
    ) -> Optional[str]:
        """Check if a request should trigger blocking using DB for shared state."""
        if not app_config.enable_blocking:
            return None

        if self._is_whitelisted(ip):
            return None

        # Check suspicious path
        is_suspicious = self._is_suspicious_path(path)
        
        # Update counters in DB and get current totals
        try:
            counts = update_request_counters(ip, status, is_suspicious)
        except Exception as e:
            logger.error(f"Failed to update request counters in DB: {e}")
            return None

        # Check thresholds
        reason = self._check_thresholds(counts)
        
        # Check CrowdSec reputation if not already blocked
        if not reason and self._crowdsec:
            if is_suspicious or status >= 400:
                if self._crowdsec.is_ip_banned(ip):
                    reason = "Bösartige IP in CrowdSec Datenbank gefunden"

        if reason:
            block_until = datetime.now(timezone.utc) + timedelta(seconds=app_config.block_duration)
            self._block_ip(ip, reason, block_until)
            logger.warning(f"Blocking IP {ip}: {reason}")
            
            # Send notification
            send_notification(ip, reason, block_until)

        return reason

    def _check_thresholds(self, counts: Dict[str, int]) -> Optional[str]:
        """Check if IP exceeds any threshold based on DB counts."""
        if counts["count_404"] >= app_config.max_404_errors:
            return f"Too many 404 errors ({counts['count_404']}/{app_config.max_404_errors})"

        if counts["count_403"] >= app_config.max_403_errors:
            return f"Too many 403 errors ({counts['count_403']}/{app_config.max_403_errors})"

        if counts["count_5xx"] >= app_config.max_5xx_errors:
            return f"Too many 5xx errors ({counts['count_5xx']}/{app_config.max_5xx_errors})"

        if counts["total_failed"] >= app_config.max_failed_requests:
            return f"Too many failed requests ({counts['total_failed']}/{app_config.max_failed_requests})"

        if counts["count_suspicious"] >= app_config.max_suspicious_paths:
            return f"Suspicious activity detected ({counts['count_suspicious']}/{app_config.max_suspicious_paths} suspicious paths)"

        return None

    def _is_suspicious_path(self, path: str) -> bool:
        """Check if path is suspicious."""
        path_lower = path.lower()
        for suspicious in app_config.suspicious_paths:
            if suspicious.lower() in path_lower:
                return True
        return False

    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is in whitelist (local cache or DB)."""
        if ip in self.whitelisted_ips:
            return True
        
        # Check DB
        try:
            whitelist = get_whitelist()
            db_ips = {row["ip_address"] for row in whitelist}
            # Update local cache
            self.whitelisted_ips.update(db_ips)
            return ip in db_ips
        except Exception:
            return False

    def _block_ip(self, ip: str, reason: str, block_until: datetime):
        """Block an IP address."""
        # Avoid redundant blocking if already in local cache
        if ip in self.blocked_ips and self.blocked_ips[ip] >= block_until:
            return

        self.blocked_ips[ip] = block_until

        # Block at firewall level if enabled
        if self.use_firewall and self._iptables:
            try:
                self._iptables.block_ip(ip, reason)
            except Exception as e:
                logger.error(f"Failed to block IP {ip} at firewall level: {e}")

        # Block at Cloudflare level if enabled
        if self._cloudflare:
            try:
                self._cloudflare.block_ip(ip, reason)
            except Exception as e:
                logger.error(f"Failed to block IP {ip} at Cloudflare level: {e}")

        # Reset counters in DB after blocking
        try:
            reset_request_counters(ip)
        except Exception as e:
            logger.error(f"Failed to reset request counters in DB: {e}")

    def is_blocked(self, ip: str) -> bool:
        """Check if an IP is currently blocked."""
        if self._is_whitelisted(ip):
            return False

        # Check local cache
        if ip in self.blocked_ips:
            if datetime.now(timezone.utc) > self.blocked_ips[ip]:
                del self.blocked_ips[ip]
                return False
            return True

        # Check firewall-level block if enabled
        if self.use_firewall and self._iptables:
            if self._iptables.is_blocked(ip):
                return True

        # Check Cloudflare-level block if enabled
        if self._cloudflare:
            return self._cloudflare.is_blocked(ip)

        return False

    def unblock_ip(self, ip: str) -> bool:
        """Manually unblock an IP."""
        unblocked = False

        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
            unblocked = True

        if self.use_firewall and self._iptables:
            try:
                if self._iptables.unblock_ip(ip):
                    unblocked = True
            except Exception as e:
                logger.error(f"Failed to unblock IP {ip} at firewall level: {e}")

        if self._cloudflare:
            try:
                if self._cloudflare.unblock_ip(ip):
                    unblocked = True
            except Exception as e:
                logger.error(f"Failed to unblock IP {ip} at Cloudflare level: {e}")

        if unblocked:
            logger.info(f"IP {ip} has been unblocked")

        return unblocked

    def whitelist_ip(self, ip: str):
        """Add IP to whitelist."""
        self.whitelisted_ips.add(ip)
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
        logger.info(f"IP {ip} added to whitelist")

    def remove_from_whitelist(self, ip: str):
        """Remove IP from whitelist."""
        self.whitelisted_ips.discard(ip)
        logger.info(f"IP {ip} removed from whitelist")

    def get_blocked_ips(self) -> Dict[str, datetime]:
        """Get all currently blocked IPs."""
        now = datetime.now(timezone.utc)
        expired = [ip for ip, until in self.blocked_ips.items() if now > until]
        for ip in expired:
            del self.blocked_ips[ip]
        return dict(self.blocked_ips)

    def get_stats(self) -> Dict:
        """Get blocking statistics."""
        return {
            "total_blocked": len(self.get_blocked_ips()),
            "whitelisted": len(self.whitelisted_ips),
            "tracked_ips": get_tracked_ip_count(),
        }

    def cleanup_old_ips(self, max_age_minutes: int = 60):
        """Cleanup old IPs from memory and DB tracker."""
        cleanup_old_trackers(max_age_minutes)
        # Memory cleanup for local cache
        now = datetime.now(timezone.utc)
        expired = [ip for ip, until in self.blocked_ips.items() if now > until]
        for ip in expired:
            del self.blocked_ips[ip]


# Global blocker instance
_blocker: Optional[IPBlocker] = None


def get_blocker(use_firewall: bool = False) -> IPBlocker:
    """Get or create the global blocker instance."""
    global _blocker
    if _blocker is None:
        _blocker = IPBlocker(use_firewall=use_firewall)
    return _blocker
