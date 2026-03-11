"""Main Streamlit application for NPM Monitor."""

import logging
import time
from datetime import datetime
from typing import Optional
from ipaddress import ip_address, ip_network

import pandas as pd
import streamlit as st

from .components import (
    render_bandwidth_analysis,
    render_charts,
    render_error_paths,
    render_geo_analysis,
    render_metrics,
    render_referer_analysis,
    render_request_log,
    render_sidebar,
    render_top_ips,
    render_user_agent_analysis,
)
from .config import app_config
from .database import (
    cleanup_old_data,
    get_database_info,
    get_distinct_hosts,
    get_newest_timestamp,
    health_check,
    load_traffic_df,
)
from .log_parser import init_geoip
from .sync import sync_logs as _sync_logs_core
from .utils import setup_logging

logger = logging.getLogger(__name__)


def check_ip_access() -> bool:
    """Check if client IP is allowed based on configured networks."""
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
    """Check authentication and IP access."""
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


def sync_logs() -> int:
    """Synchronize logs and invalidate cached data used by the UI."""
    inserted = _sync_logs_core()
    # Invalidate caches so new data is visible immediately
    load_traffic_data.clear()
    _cached_hosts.clear()
    _cached_db_info.clear()
    return inserted


@st.cache_data(ttl=30)
def load_traffic_data(
    hosts: Optional[tuple] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50000,
) -> pd.DataFrame:
    """Load traffic data from database with filters."""
    return load_traffic_df(
        hosts=list(hosts) if hosts else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@st.cache_data(ttl=60)
def _cached_hosts():
    return get_distinct_hosts()


@st.cache_data(ttl=60)
def _cached_db_info():
    return get_database_info()


def get_newest():
    return get_newest_timestamp()


def main():
    """Main application entry point."""
    setup_logging()

    st.set_page_config(
        page_title="NPM Monitor",
        page_icon="🌐",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Check authentication
    if not check_auth():
        return

    # Initialize GeoIP
    init_geoip()

    # Header with sync button (10s cooldown)
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🌐 NPM Traffic Monitor")
        last_sync_ts = st.session_state.get("last_sync_time", 0)
        if last_sync_ts > 0:
            last_sync_dt = datetime.fromtimestamp(last_sync_ts)
            st.caption(f"Letzter Sync: {last_sync_dt.strftime('%H:%M:%S')}")
    with col2:
        cooldown_remaining = 10 - (time.time() - last_sync_ts)
        sync_disabled = cooldown_remaining > 0

        if st.button("🔄 Sync", width="stretch", disabled=sync_disabled):
            with st.spinner("Synchronisiere..."):
                new_rows = sync_logs()
                st.session_state.last_sync_time = time.time()
                st.toast(f"{new_rows} neue Einträge", icon="✅")
            st.rerun()

    # Health check
    if not health_check():
        st.error("Datenbankverbindung fehlgeschlagen!")
        return

    # Auto-sync on first load
    if "synced" not in st.session_state:
        with st.spinner("Initiale Synchronisation..."):
            new_rows = sync_logs()
            st.session_state.synced = True
            st.session_state.last_sync_time = time.time()
            if new_rows > 0:
                st.toast(f"{new_rows} neue Einträge", icon="✅")

    # Sidebar filters
    selected_hosts, start_date, end_date, auto_refresh, refresh_interval, search_query, selected_status = (
        render_sidebar(
            cached_hosts=_cached_hosts,
            cached_db_info=_cached_db_info,
            get_newest_timestamp=get_newest,
            sync_logs_callback=sync_logs,
            cleanup_old_data_callback=cleanup_old_data,
        )
    )

    # Handle empty host selection
    if not selected_hosts:
        st.warning("Bitte wähle mindestens eine Domain aus.")
        return

    # Load data
    with st.spinner("Lade Daten..."):
        df = load_traffic_data(
            hosts=tuple(selected_hosts),
            start_date=start_date,
            end_date=end_date,
            limit=app_config.max_display_rows,
        )

    # Apply status code filter
    status_ranges = {
        "2xx Erfolg": (200, 299),
        "3xx Redirect": (300, 399),
        "4xx Client-Fehler": (400, 499),
        "5xx Server-Fehler": (500, 599),
    }
    if selected_status != "Alle" and selected_status in status_ranges:
        low, high = status_ranges[selected_status]
        df = df[(df["status"] >= low) & (df["status"] <= high)]

    # Apply search filter
    if search_query:
        mask = (
            df["remote_addr"].str.contains(search_query, case=False, na=False)
            | df["host"].str.contains(search_query, case=False, na=False)
            | df["path"].str.contains(search_query, case=False, na=False)
        )
        df = df[mask]

    if df.empty:
        st.info("Keine Daten für den ausgewählten Filter gefunden.")
        return

    # Render dashboard
    render_dashboard(df, auto_refresh, refresh_interval)


def render_dashboard(df: pd.DataFrame, auto_refresh: bool, refresh_interval: int):
    """Render the main dashboard components."""
    render_metrics(df)
    st.divider()
    render_charts(df)
    render_top_ips(df)
    render_error_paths(df)
    render_bandwidth_analysis(df)
    render_geo_analysis(df)
    render_referer_analysis(df)
    render_user_agent_analysis(df)
    render_request_log(df)

    # Auto-refresh: sync new data and rerun
    if auto_refresh:
        time.sleep(refresh_interval)
        sync_logs()
        st.rerun()


if __name__ == "__main__":
    main()
