"""Shared UI utilities for Streamlit pages."""

import time
import logging
import streamlit as st
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from .config import app_config
from .database import (
    get_distinct_hosts,
    get_database_info,
    get_newest_timestamp,
    health_check,
    cleanup_old_data,
    load_traffic_df,
    get_traffic_count,
    get_hourly_traffic_summary,
    get_top_ips_summary
)
from .sync import sync_logs as _sync_logs_core
from .log_parser import init_geoip
from .utils import setup_logging
from .components import render_sidebar

logger = logging.getLogger(__name__)


def init_page(title: str, icon: str = "🌐"):
    """Initialize a Streamlit page with standard config and health check."""
    st.set_page_config(
        page_title=f"NPM Monitor - {title}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    setup_logging()
    init_geoip()
    
    if not health_check():
        st.error("Datenbankverbindung fehlgeschlagen!")
        st.stop()


def sync_logs() -> int:
    """Synchronize logs and invalidate cached data."""
    inserted = _sync_logs_core()
    # Invalidate caches
    load_traffic_data.clear()
    _cached_hosts.clear()
    _cached_db_info.clear()
    _cached_hourly_summary.clear()
    _cached_top_ips.clear()
    return inserted


@st.cache_data(ttl=300)
def load_traffic_data(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 1000,
    offset: int = 0,
):
    """Cached traffic data loading with explicit parameters for better caching."""
    return load_traffic_df(
        hosts=list(hosts) if hosts else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )


@st.cache_data(ttl=300)
def _cached_hosts():
    return get_distinct_hosts()


@st.cache_data(ttl=300)
def _cached_db_info():
    return get_database_info()


@st.cache_data(ttl=300)
def _cached_hourly_summary(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    return get_hourly_traffic_summary(
        hosts=list(hosts) if hosts else None,
        start_date=start_date,
        end_date=end_date,
    )


@st.cache_data(ttl=300)
def _cached_top_ips(
    hosts: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
):
    return get_top_ips_summary(
        hosts=list(hosts) if hosts else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


def render_common_sidebar():
    """Render the standard sidebar and return filter values."""
    return render_sidebar(
        cached_hosts=_cached_hosts,
        cached_db_info=_cached_db_info,
        get_newest_timestamp=get_newest_timestamp,
        sync_logs_callback=sync_logs,
        cleanup_old_data_callback=cleanup_old_data,
    )


def handle_sync_button():
    """Render the sync button in the header."""
    col1, col2 = st.columns([4, 1])
    with col1:
        last_sync_ts = st.session_state.get("last_sync_time", 0)
        if last_sync_ts > 0:
            last_sync_dt = datetime.fromtimestamp(last_sync_ts, timezone.utc)
            st.caption(f"Letzter Sync: {last_sync_dt.strftime('%H:%M:%S')}")
    with col2:
        cooldown_remaining = 10 - (time.time() - last_sync_ts)
        sync_disabled = cooldown_remaining > 0

        if st.button("🔄 Sync", width="stretch", disabled=sync_disabled, key="header_sync"):
            with st.spinner("Synchronisiere..."):
                new_rows = sync_logs()
                st.session_state.last_sync_time = time.time()
                st.toast(f"{new_rows} neue Einträge", icon="✅")
            st.rerun()
