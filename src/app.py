"""Main Streamlit application for NPM Monitor."""

import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

from .auth import check_auth
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
    get_hourly_traffic_summary,
    get_newest_timestamp,
    get_top_ips_summary,
    get_traffic_count,
    health_check,
    load_traffic_df,
)
from .log_parser import init_geoip
from .sync import sync_logs as _sync_logs_core
from .utils import setup_logging

logger = logging.getLogger(__name__)


def sync_logs() -> int:
    """Synchronize logs and invalidate cached data used by the UI."""
    inserted = _sync_logs_core()
    # Invalidate caches so new data is visible immediately
    load_traffic_data.clear()
    _cached_hosts.clear()
    _cached_db_info.clear()
    _cached_hourly_summary.clear()
    _cached_top_ips.clear()
    return inserted


@st.cache_data(ttl=300)  # Increased from 30s to 5 minutes
def load_traffic_data(
    hosts: Optional[tuple] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 10000,  # Reduced from 50000 for better performance
    offset: int = 0,
) -> pd.DataFrame:
    """Load traffic data from database with filters and pagination."""
    return load_traffic_df(
        hosts=list(hosts) if hosts else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@st.cache_data(ttl=300)  # Increased from 60s to 5 minutes
def _cached_hosts():
    return get_distinct_hosts()


@st.cache_data(ttl=300)  # Increased from 60s to 5 minutes
def _cached_db_info():
    return get_database_info()


@st.cache_data(ttl=300)
def _cached_hourly_summary(
    hosts: Optional[tuple] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """Get cached hourly traffic summary (much faster than full data)."""
    return get_hourly_traffic_summary(
        hosts=list(hosts) if hosts else None,
        start_date=start_date,
        end_date=end_date,
    )


@st.cache_data(ttl=300)
def _cached_top_ips(
    hosts: Optional[tuple] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
) -> pd.DataFrame:
    """Get cached top IPs summary (aggregated, faster)."""
    return get_top_ips_summary(
        hosts=list(hosts) if hosts else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


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

    # Load data with pagination
    with st.spinner("Lade Daten..."):
        # Get total count for pagination info
        total_count = get_traffic_count(
            hosts=selected_hosts,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Load paginated data (smaller chunks for better performance)
        df = load_traffic_data(
            hosts=tuple(selected_hosts),
            start_date=start_date,
            end_date=end_date,
            limit=10000,  # Reduced limit for faster loading
            offset=0,
        )
        
        # Show pagination info if data is truncated
        if total_count > len(df):
            st.info(f"Zeige {len(df)} von {total_count} Einträgen. Verwende Filter für präzisere Ergebnisse.")

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

    # Load optimized summaries for charts (much faster)
    hourly_summary = _cached_hourly_summary(
        hosts=tuple(selected_hosts),
        start_date=start_date,
        end_date=end_date,
    )
    
    top_ips_summary = _cached_top_ips(
        hosts=tuple(selected_hosts),
        start_date=start_date,
        end_date=end_date,
        limit=100,
    )

    # Render dashboard with optimized data
    render_dashboard(df, hourly_summary, top_ips_summary, auto_refresh, refresh_interval)


def render_dashboard(df: pd.DataFrame, hourly_summary: pd.DataFrame, top_ips_summary: pd.DataFrame, auto_refresh: bool, refresh_interval: int):
    """Render the main dashboard components with optimized data."""
    # Create tabs for main content and blocked IPs
    tab1, tab2 = st.tabs(["📊 Dashboard", "🚫 Blocked IPs"])
    
    with tab1:
        render_metrics(df)
        st.divider()
        # Use optimized summaries for charts where possible
        render_charts(df, hourly_summary)
        render_top_ips(df, top_ips_summary)
        render_error_paths(df)
        render_bandwidth_analysis(df)
        render_geo_analysis(df)
        render_referer_analysis(df)
        render_user_agent_analysis(df)
        render_request_log(df)
    
    with tab2:
        from .components.blocking import render_blocked_ips, render_blocking_config
        render_blocked_ips()
        st.divider()
        render_blocking_config()

    # Non-blocking auto-refresh using session state
    if auto_refresh:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = time.time()
        
        elapsed = time.time() - st.session_state.last_refresh
        if elapsed >= refresh_interval:
            st.session_state.last_refresh = time.time()
            sync_logs()
            st.rerun()
        else:
            # Show countdown
            remaining = int(refresh_interval - elapsed)
            st.caption(f"🔄 Auto-refresh in {remaining}s")


if __name__ == "__main__":
    main()
