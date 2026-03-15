"""Authentication module for NPM Monitor."""

import logging
import hashlib
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from typing import Dict, List, Tuple, Optional

import streamlit as st

from .config import app_config
from .database import get_user, create_user

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """Hash a password with a salt."""
    salt = os.getenv("AUTH_SALT", "default_salt_123")
    return hashlib.sha256((password + salt).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    return hash_password(password) == hashed

def create_initial_admin():
    """Ensure at least one admin user exists based on config."""
    if not get_user(app_config.auth_username):
        hashed = hash_password(app_config.auth_password)
        create_user(app_config.auth_username, hashed, role="admin")
        logger.info(f"Initial admin user '{app_config.auth_username}' created.")

# Rate limiting storage: IP -> (failed_attempts, first_attempt_time, blocked_until)
_login_attempts: Dict[str, Tuple[int, datetime, datetime]] = defaultdict(lambda: (0, datetime.now(timezone.utc), datetime.fromtimestamp(0, timezone.utc)))

# Rate limiting configuration
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 15
BLOCK_DURATION_MINUTES = 30


def check_ip_access() -> bool:
    """Check if client IP is allowed based on configured networks.
    
    Returns:
        True if access is allowed, False otherwise.
    """
    if not hasattr(st, "_client_ip"):
        try:
            import streamlit.runtime.scriptrunner.script_run_context as ctx
            session_info = ctx.get_script_run_ctx().session_info
            st._client_ip = session_info.client_ip if session_info else "127.0.0.1"
        except (AttributeError, ImportError):
            st._client_ip = "127.0.0.1"
    
    client_ip = st._client_ip
    if not app_config.allowed_networks:
        return True
    
    for network_str in app_config.allowed_networks:
        network_str = network_str.strip()
        if not network_str:
            continue
        try:
            network = ip_network(network_str)
            if ip_address(client_ip) in network:
                return True
        except (ValueError, TypeError):
            continue
    
    logger.warning(f"Access denied for IP: {client_ip}")
    return False


def _get_client_ip() -> str:
    """Get client IP address."""
    if not hasattr(st, "_client_ip"):
        try:
            import streamlit.runtime.scriptrunner.script_run_context as ctx
            session_info = ctx.get_script_run_ctx().session_info
            st._client_ip = session_info.client_ip if session_info else "127.0.0.1"
        except (AttributeError, ImportError):
            st._client_ip = "127.0.0.1"
    return st._client_ip


def _check_rate_limit(ip: str) -> Tuple[bool, int]:
    """Check if IP is rate limited.
    
    Returns:
        Tuple of (is_allowed, minutes_remaining)
    """
    now = datetime.now(timezone.utc)
    attempts, first_attempt, blocked_until = _login_attempts[ip]
    
    # Check if currently blocked
    if now < blocked_until:
        minutes_remaining = int((blocked_until - now).total_seconds() / 60)
        return False, minutes_remaining
    
    # Reset if window has passed
    if now - first_attempt > timedelta(minutes=LOGIN_WINDOW_MINUTES):
        _login_attempts[ip] = (0, now, datetime.min)
        return True, 0
    
    return True, 0


def _record_failed_attempt(ip: str):
    """Record a failed login attempt."""
    now = datetime.now(timezone.utc)
    attempts, first_attempt, _ = _login_attempts[ip]
    
    # Reset if window has passed
    if now - first_attempt > timedelta(minutes=LOGIN_WINDOW_MINUTES):
        attempts = 0
        first_attempt = now
    
    attempts += 1
    
    # Block if too many attempts
    if attempts >= MAX_LOGIN_ATTEMPTS:
        blocked_until = now + timedelta(minutes=BLOCK_DURATION_MINUTES)
        _login_attempts[ip] = (attempts, first_attempt, blocked_until)
        logger.warning(f"Rate limited IP {ip} after {attempts} failed attempts")
    else:
        _login_attempts[ip] = (attempts, first_attempt, datetime.min)


def _record_successful_attempt(ip: str):
    """Clear failed attempts after successful login."""
    if ip in _login_attempts:
        del _login_attempts[ip]


import pyotp

def check_auth() -> bool:
    """Check authentication and IP access.
    
    Returns:
        True if authenticated and authorized, False otherwise.
    """
    if not app_config.enable_auth:
        return True
    
    if not check_ip_access():
        st.error("Access denied: Your IP address is not allowed.")
        return False
    
    # Initialize initial admin if table is empty
    create_initial_admin()
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        client_ip = _get_client_ip()
        
        # Check rate limiting
        is_allowed, minutes_remaining = _check_rate_limit(client_ip)
        if not is_allowed:
            st.error(f"Too many failed attempts. Please try again in {minutes_remaining} minutes.")
            logger.warning(f"Rate limited login attempt from {client_ip}")
            return False
        
        with st.container():
            st.title("🔐 NPM Monitor Login")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                username = st.text_input("Username", key="auth_username")
                password = st.text_input("Password", type="password", key="auth_password")
                totp_code = st.text_input("MFA Code (falls aktiviert)", key="auth_totp", help="Lass dieses Feld leer, wenn du kein MFA aktiviert hast.")
                
                if st.button("Login", type="primary"):
                    user = get_user(username)
                    if user and verify_password(password, user["password_hash"]):
                        # Check TOTP if enabled
                        if user.get("totp_secret"):
                            totp = pyotp.TOTP(user["totp_secret"])
                            if not totp.verify(totp_code):
                                st.error("Ungültiger MFA Code.")
                                _record_failed_attempt(client_ip)
                                return False
                                
                        _record_successful_attempt(client_ip)
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        
                        # Auto-Whitelist admin IP
                        try:
                            from .blocking import get_blocker
                            blocker = get_blocker()
                            blocker.whitelist_ip(client_ip)
                            # Also persist to DB if possible
                            from .database import add_to_whitelist
                            add_to_whitelist(client_ip, f"Auto-Whitelist via MFA Login ({username})")
                            logger.info(f"IP {client_ip} auto-whitelisted after successful login for user {username}")
                        except Exception as e:
                            logger.error(f"Failed to auto-whitelist IP: {e}")
                            
                        st.rerun()
                    else:
                        _record_failed_attempt(client_ip)
                        remaining = MAX_LOGIN_ATTEMPTS - _login_attempts[client_ip][0]
                        if remaining > 0:
                            st.error(f"Invalid credentials. {remaining} attempts remaining.")
                        else:
                            st.error(f"Too many failed attempts. Please try again in {BLOCK_DURATION_MINUTES} minutes.")
            
            st.info("Please contact your administrator for access.")
            return False
    
    return True