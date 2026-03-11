"""Authentication module for NPM Monitor."""

import logging
from ipaddress import ip_address, ip_network
from typing import List

import streamlit as st

from .config import app_config

logger = logging.getLogger(__name__)


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
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        with st.container():
            st.title("🔐 NPM Monitor Login")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                username = st.text_input("Username", key="auth_username")
                password = st.text_input("Password", type="password", key="auth_password")
                
                if st.button("Login", type="primary"):
                    if (username == app_config.auth_username and 
                        password == app_config.auth_password):
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
            
            st.info("Please contact your administrator for access.")
            return False
    
    return True