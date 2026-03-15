"""IP blocking module for automatic threat detection and blocking."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

from .config import app_config
from .database import (
    cleanup_trackers,
    get_asn_blocklist,
    get_blocked_ips,
    get_ip_block_count,
    get_tracked_ip_count,
    get_whitelist,
    reset_request_counters,
    update_request_counters,
)
from .notifications import send_notification
from .utils.whois import get_whois_info

logger = logging.getLogger(__name__)


class IPBlocker:
    """Automatic IP blocking based on attack patterns with shared state in DB."""

    def __init__(self, use_firewall: bool = False):
        self.blocked_ips: Dict[str, datetime] = {}  # IP -> block_until (local cache)
        self.whitelisted_ips: Set[str] = set()
        self.blocked_asns: Set[str] = set()
        self.ip_asn_cache: Dict[str, str] = {}  # IP -> ASN cache
        self.use_firewall = use_firewall
        self._last_list_refresh = 0.0

        # Initialize firewall manager if enabled
        self._iptables = None
        if use_firewall:
            try:
                from .firewall import get_iptables_manager

                self._iptables = get_iptables_manager()
                if self._iptables.has_permissions or self._iptables.use_sudo:
                    logger.info("Firewall-level blocking enabled (iptables)")
                    self._iptables.create_chain()
                    # Task 1: Restore rules from DB
                    self.restore_firewall_rules()
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

    def restore_firewall_rules(self):
        """Task 1: Restore active blocks from database to firewall upon startup."""
        if not self.use_firewall or not self._iptables:
            return

        try:
            active_blocks = get_blocked_ips(active_only=True)
            if not active_blocks:
                return

            logger.info(f"Restoring {len(active_blocks)} active blocks to firewall...")
            count = 0
            for ip, reason, _, _, _, _ in active_blocks:
                if self._iptables.block_ip(ip, f"RESTORED: {reason}"):
                    count += 1
            logger.info(f"Successfully restored {count} firewall rules.")
        except Exception as e:
            logger.error(f"Failed to restore firewall rules: {e}")

    def _refresh_lists_if_needed(self, force: bool = False):
        """Refresh whitelists and blocklists periodically to avoid DB hammering."""
        import time

        now = time.time()
        if not force and now - self._last_list_refresh < 60:  # Refresh every 60 seconds
            return

        try:
            # Task 4: Optimized batch-loading for whitelist
            whitelist = get_whitelist()
            self.whitelisted_ips = {row["ip_address"] for row in whitelist}

            # Refresh ASN blocklist
            asn_list = get_asn_blocklist()
            self.blocked_asns = {str(row["asn"]) for row in asn_list}

            self._last_list_refresh = now
        except Exception as e:
            logger.error(f"Failed to refresh blocking lists: {e}")

    def _is_asn_blocked(self, ip: str) -> bool:
        """Check if IP belongs to a blocked ASN."""
        self._refresh_lists_if_needed()
        if not self.blocked_asns:
            return False

        # Get ASN for this IP
        asn = self.ip_asn_cache.get(ip)
        if not asn:
            # Slow lookup, only do once per IP per session
            try:
                whois = get_whois_info(ip)
                if whois and whois.get("asn"):
                    asn = str(whois["asn"])
                    self.ip_asn_cache[ip] = asn
            except Exception:
                return False

        # Check if ASN is in blocklist
        return asn in self.blocked_asns

    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is in whitelist (local cache or DB)."""
        self._refresh_lists_if_needed()
        return ip in self.whitelisted_ips

    def _block_ip(self, ip: str, reason: str, block_until: datetime):
        """Block an IP address."""
        # 3. Dry-Run Check
        if app_config.waf_dry_run:
            logger.info(f"[DRY-RUN] Would block IP {ip} until {block_until}. Reason: {reason}")
            return

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

    def _get_adaptive_duration(self, ip: str) -> int:
        """Calculate adaptive block duration based on previous blocks."""
        base_duration = app_config.block_duration
        if not app_config.enable_adaptive_blocking:
            return base_duration

        # Get number of previous blocks from DB
        try:
            previous_blocks = get_ip_block_count(ip)

            if previous_blocks <= 1:
                return base_duration
            elif previous_blocks == 2:
                return 86400  # 1 day
            elif previous_blocks == 3:
                return 604800  # 1 week
            else:
                return 31536000  # 1 year (permanent-ish)
        except Exception:
            return base_duration

    def check_request(
        self, ip: str, status: int, path: str, host: str = "", user_agent: str = "", country_code: Optional[str] = None
    ) -> Optional[str]:
        """Check if a request should trigger blocking using DB for shared state."""
        if not app_config.enable_blocking:
            return None

        if self._is_whitelisted(ip):
            return None

        # 0. Check for ASN block
        if self._is_asn_blocked(ip):
            reason = "ASN ist blockiert (Netzwerk-Sperre)"
            return reason

        # 0.05 CrowdSec Reputation Check
        if app_config.enable_crowdsec and self._crowdsec:
            decision = self._crowdsec.get_ip_reputation(ip)
            if decision:
                reason = f"CrowdSec Reputations-Sperre: {decision.get('type', 'Banned')}"
                # Adaptive 24h block for CrowdSec listed IPs
                block_until = datetime.now(timezone.utc) + timedelta(days=1)
                self._block_ip(ip, reason, block_until)
                logger.warning(f"CROWDSEC BLOCK for IP {ip}: {reason}")
                send_notification(ip, reason, block_until)
                return reason

        # 0.1 Geo-Blocking Check
        if country_code:
            # Check if country is explicitly blocked
            if country_code in app_config.blocked_countries:
                reason = f"Land {country_code} ist gesperrt (Geo-Blocking)"
                # 24h block
                block_until = datetime.now(timezone.utc) + timedelta(days=1)
                self._block_ip(ip, reason, block_until)
                return reason

            # Check if only specific countries are allowed
            if app_config.allow_only_countries and country_code not in app_config.allow_only_countries:
                reason = f"Land {country_code} ist nicht in der Erlaubt-Liste (Geo-Blocking)"
                # 24h block
                block_until = datetime.now(timezone.utc) + timedelta(days=1)
                self._block_ip(ip, reason, block_until)
                return reason

        # 0.2 Fake Bot Check (Reverse DNS)
        if "bot" in user_agent.lower() or "google" in user_agent.lower() or "bing" in user_agent.lower():
            if not self._is_verified_bot(ip, user_agent):
                reason = f"Fake Bot erkannt (User-Agent Spoofing): {user_agent}"
                # 7-day block for fake bots
                block_until = datetime.now(timezone.utc) + timedelta(days=7)
                self._block_ip(ip, reason, block_until)
                logger.warning(f"SPOOFING DETECTED: IP {ip} claims to be {user_agent}")
                return reason

        # 0.3 Context & ASN Multiplier
        multiplier = 1.0
        if self._is_sensitive_path(path):
            multiplier *= 3.0  # Errors on sensitive paths are much worse

        if self._is_datacenter_asn(ip):
            multiplier *= 2.0  # Traffic from Data Centers is more suspicious

        # WAF: User-Agent Check
        if self._is_malicious_user_agent(user_agent):
            reason = f"Bösartiger User-Agent erkannt: {user_agent}"
            # Use adaptive duration
            duration = self._get_adaptive_duration(ip)
            block_until = datetime.now(timezone.utc) + timedelta(seconds=duration)
            self._block_ip(ip, reason, block_until)
            logger.warning(f"INSTANT BLOCK (WAF) for IP {ip}: {reason}")
            send_notification(ip, reason, block_until)
            return reason

        # WAF: Pattern Check (Task 3: Modern threats)
        waf_reason = self._check_waf_rules(path, user_agent)
        if waf_reason:
            duration = self._get_adaptive_duration(ip)
            block_until = datetime.now(timezone.utc) + timedelta(seconds=duration)
            self._block_ip(ip, waf_reason, block_until)
            logger.warning(f"INSTANT BLOCK (WAF) for IP {ip}: {waf_reason}")
            send_notification(ip, waf_reason, block_until)
            return waf_reason

        # 1. Deceptive Defense: Honey-Paths (Custom/Long-term ban)
        if self._is_honey_path(path):
            reason = f"Honeypot ausgelöst: {path}"
            # Long-term block for accessing critical bait paths
            block_until = datetime.now(timezone.utc) + timedelta(seconds=app_config.honey_pot_duration)
            self._block_ip(ip, reason, block_until)
            logger.warning(f"DECEPTIVE DEFENSE: LONG-TERM BLOCK for IP {ip}: {reason}")
            send_notification(ip, reason, block_until)
            return reason

        # 2. Regular suspicious path check
        is_suspicious = self._is_suspicious_path(path)

        # Update counters in DB and get current totals
        try:
            # We apply the multiplier manually to the threat score increment
            counts = update_request_counters(ip, status, is_suspicious)

            # Apply multiplier to existing increment logic
            if multiplier > 1.0:
                score_to_add = 0
                if is_suspicious:
                    score_to_add = 30 * (multiplier - 1)
                elif status == 403:
                    score_to_add = 20 * (multiplier - 1)
                elif status == 404:
                    score_to_add = 5 * (multiplier - 1)

                if score_to_add > 0:
                    from .database import update_threat_score

                    update_threat_score(ip, int(score_to_add))
                    # Refresh counts
                    from .database import get_redis

                    counts["threat_score"] = int(get_redis().hget(f"tracker:{ip}", "threat_score") or 0)

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
            duration = self._get_adaptive_duration(ip)
            block_until = datetime.now(timezone.utc) + timedelta(seconds=duration)
            self._block_ip(ip, reason, block_until)
            logger.warning(f"Blocking IP {ip}: {reason} (Duration: {duration}s)")

            # Send notification
            send_notification(ip, reason, block_until)

        return reason

    def _is_malicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent matches known malicious actors or scanners."""
        if not user_agent or user_agent == "-":
            return False

        ua_lower = user_agent.lower()
        bad_uas = [
            "zgrab",
            "masscan",
            "nmap",
            "sqlmap",
            "nikto",
            "dirbuster",
            "netsparker",
            "wpscan",
            "nuclei",
            "censys",
            "shodan",
            "mirai",
            "hello, world",
            "gobuster",
            "ffuf",
            "ffuf/",
            "python-requests/2.6",
            "masscan/1.0",
        ]
        return any(bad_ua in ua_lower for bad_ua in bad_uas)

    def _check_waf_rules(self, path: str, user_agent: str = "") -> Optional[str]:
        """Task 3: Check for SQLi, XSS, Path Traversal, and Modern Threats (Log4Shell, etc.)."""
        if not path:
            return None

        combined_input = (path + " " + user_agent).lower()

        # 1. SQLi heuristic
        sqli_patterns = [
            "union select",
            "union all select",
            "' or '1'='1",
            '" or "1"="1',
            "@@version",
            "information_schema",
            "sysobjects",
            "syscolumns",
            "waitfor delay",
            "pg_sleep(",
        ]
        if any(pattern in combined_input for pattern in sqli_patterns):
            return "SQL-Injection Versuch (WAF Heuristik)"

        # 2. XSS heuristic
        xss_patterns = ["<script", "%3cscript", "javascript:", "onerror=", "onload=", "alert("]
        if any(pattern in combined_input for pattern in xss_patterns):
            return "XSS Versuch (WAF Heuristik)"

        # 3. Path Traversal & LFI
        traversal_patterns = [
            "../",
            "..\\",
            "/etc/passwd",
            "/etc/shadow",
            "/etc/group",
            "c:\\windows",
            "boot.ini",
            "/proc/self",
            "file_get_contents",
            "include(",
        ]
        if any(pattern in combined_input for pattern in traversal_patterns):
            return "Path Traversal / LFI Versuch (WAF Heuristik)"

        # 4. Modern Threats & Exploits
        modern_exploits = {
            "${jndi:ldap": "Log4Shell Exploit Versuch (CVE-2021-44228)",
            "${jndi:dns": "Log4Shell Exploit Versuch (CVE-2021-44228)",
            "class.module.classloader": "SpringShell Exploit Versuch (CVE-2022-22965)",
            "/cgi-bin/": "CGI-BIN Scan / Exploit Versuch",
            "() { :; };": "Shellshock Exploit Versuch (CVE-2014-6271)",
            ".aws/credentials": "Cloud Credential Theft Versuch",
            ".ssh/id_rsa": "SSH Key Theft Versuch",
        }
        for pattern, reason in modern_exploits.items():
            if pattern in combined_input:
                return reason

        # 5. Command Injection
        cmd_patterns = [
            "; curl ",
            "; wget ",
            "; chmod ",
            "; chown ",
            "; rm -rf",
            "| curl ",
            "| wget ",
            "| chmod ",
            "`curl ",
            "`wget ",
        ]
        if any(pattern in combined_input for pattern in cmd_patterns):
            return "Command Injection Versuch (WAF Heuristik)"

        return None

    def _is_sensitive_path(self, path: str) -> bool:
        """Check if path is highly sensitive (Login, Admin, etc.)."""
        path_lower = path.lower()
        for sensitive in app_config.sensitive_paths:
            if sensitive.lower() in path_lower:
                return True
        return False

    def _is_datacenter_asn(self, ip: str) -> bool:
        """Heuristic to check if an IP belongs to a Data Center (hosting provider)."""
        try:
            whois = get_whois_info(ip)
            if not whois:
                return False

            desc = whois.get("asn_description", "").lower()
            net_name = whois.get("network_name", "").lower()

            # Known Data Center / Hosting keywords
            dc_keywords = [
                "hetzner",
                "digitalocean",
                "amazon",
                "aws",
                "google cloud",
                "ovh",
                "linode",
                "vultr",
                "leaseweb",
                "contabo",
                "intergrid",
                "hosting",
                "server",
                "cloud",
                "datacenter",
                "m247",
                "akamai",
            ]

            for kw in dc_keywords:
                if kw in desc or kw in net_name:
                    return True
        except Exception:
            pass

        return False

    def _check_thresholds(self, counts: Dict[str, int]) -> Optional[str]:
        """Check if IP exceeds any threshold based on DB counts or threat score."""
        # 0. Check threat score (new system)
        threat_score = counts.get("threat_score", 0)
        if threat_score >= 100:
            return f"Behavioral threat score reached threshold ({threat_score}/100)"

        if counts["count_404"] >= app_config.max_404_errors:
            return f"Too many 404 errors ({counts['count_404']}/{app_config.max_404_errors})"

        if counts["count_403"] >= app_config.max_403_errors:
            return f"Too many 403 errors ({counts['count_403']}/{app_config.max_403_errors})"

        if counts["count_5xx"] >= app_config.max_5xx_errors:
            return f"Too many 5xx errors ({counts['count_5xx']}/{app_config.max_5xx_errors})"

        if counts["total_failed"] >= app_config.max_failed_requests:
            return f"Too many failed requests ({counts['total_failed']}/{app_config.max_failed_requests})"

        if counts["count_suspicious"] >= app_config.max_suspicious_paths:
            return (
                f"Suspicious activity detected "
                f"({counts['count_suspicious']}/{app_config.max_suspicious_paths} suspicious paths)"
            )

        # Rate Limit Check (total requests per 5 minutes)
        if counts["total_requests"] >= (app_config.max_requests_per_minute * 5):
            return f"Rate limit exceeded ({counts['total_requests']} req/5min)"

        return None

    def _is_verified_bot(self, ip: str, user_agent: str) -> bool:
        """Verify if a bot claiming to be Google/Bing is actually from them using RDNS."""
        import socket

        ua_lower = user_agent.lower()

        # Check for Googlebot
        if "googlebot" in ua_lower:
            try:
                # 1. Reverse DNS (IP -> Hostname)
                hostname, _, _ = socket.gethostbyaddr(ip)
                # 2. Verify domain ends with .googlebot.com or .google.com
                if not (hostname.endswith(".googlebot.com") or hostname.endswith(".google.com")):
                    return False
                # 3. Forward DNS (Hostname -> IP) to prevent DNS Spoofing
                verified_ip = socket.gethostbyname(hostname)
                return verified_ip == ip
            except Exception:
                return False

        # Check for Bingbot
        if "bingbot" in ua_lower:
            try:
                hostname, _, _ = socket.gethostbyaddr(ip)
                if not hostname.endswith(".search.msn.com"):
                    return False
                verified_ip = socket.gethostbyname(hostname)
                return verified_ip == ip
            except Exception:
                return False

        return True

    def _is_suspicious_path(self, path: str) -> bool:
        """Check if path is suspicious."""
        path_lower = path.lower()
        for suspicious in app_config.suspicious_paths:
            if suspicious.lower() in path_lower:
                return True
        return False

    def _is_honey_path(self, path: str) -> bool:
        """Check if path is a honey path (immediate 1-year ban for critical bait)."""
        path_lower = path.lower()

        # Enterprise Bait Paths
        bait_paths = [
            "/.env",
            "/.git",
            "/wp-config.php",
            "/config.php",
            "/phpmyadmin",
            "/myadmin",
            "/pma",
            "/admin/config.php",
            "/backup.sql",
            "/dump.sql",
            "/.aws/credentials",
            "/.ssh/id_rsa",
        ]

        for honey in bait_paths:
            if honey.lower() == path_lower or honey.lower() in path_lower:
                return True

        # User defined honey paths
        for honey in app_config.honey_paths:
            if honey.lower() == path_lower or honey.lower() in path_lower:
                return True
        return False

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
            # Audit log
            from streamlit import session_state

            username = session_state.get("user", {}).get("username", "system")
            from .database import add_audit_log

            add_audit_log(username, "UNBLOCK", ip, "Manuelle Entsperrung via Dashboard")

        return unblocked

    def whitelist_ip(self, ip: str, reason: str = "Manual whitelist"):
        """Add IP to whitelist."""
        self.whitelisted_ips.add(ip)
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
        logger.info(f"IP {ip} added to whitelist")

        # Audit log
        from streamlit import session_state

        username = session_state.get("user", {}).get("username", "system")
        from .database import add_audit_log

        add_audit_log(username, "WHITELIST_ADD", ip, reason)

    def remove_from_whitelist(self, ip: str):
        """Remove IP from whitelist."""
        self.whitelisted_ips.discard(ip)
        logger.info(f"IP {ip} removed from whitelist")

        # Audit log
        from streamlit import session_state

        username = session_state.get("user", {}).get("username", "system")
        from .database import add_audit_log

        add_audit_log(username, "WHITELIST_REMOVE", ip)

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
        cleanup_trackers(max_age_minutes)
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
