"""Sidebar component for Streamlit application."""

from datetime import datetime, timedelta
from typing import Callable, List, Tuple

import streamlit as st

from ..config import app_config
from ..utils import format_number, get_relative_time, get_time_ranges


def render_sidebar(
    cached_hosts: Callable[[], List[str]],
    cached_db_info: Callable[[], dict],
    get_newest_timestamp: Callable[[], datetime],
    sync_logs_callback: Callable[[], int],
    cleanup_old_data_callback: Callable[[], int],
) -> Tuple[List[str], datetime, datetime, bool, int, str, str]:
    """Render sidebar with filters and return selected values."""
    st.sidebar.header("Filter")

    # Time range selection
    time_ranges = get_time_ranges()
    selected_range = st.sidebar.selectbox(
        "Zeitraum",
        options=list(time_ranges.keys()),
        index=2,  # Default: Letzte 24 Stunden
    )
    start_date, end_date = time_ranges[selected_range]

    # Custom date range
    if st.sidebar.checkbox("Eigenen Zeitraum wählen"):
        col1, col2 = st.sidebar.columns(2)
        with col1:
            custom_start = st.date_input("Von", value=datetime.now().date() - timedelta(days=7))
        with col2:
            custom_end = st.date_input("Bis", value=datetime.now().date())
        start_date = datetime.combine(custom_start, datetime.min.time())
        end_date = datetime.combine(custom_end, datetime.max.time())

    # Host filter
    hosts = cached_hosts()
    selected_hosts = st.sidebar.multiselect(
        "Domains", options=hosts, default=hosts, help="Wähle die Domains aus, die angezeigt werden sollen"
    )

    # Status code filter
    status_options = ["Alle", "2xx Erfolg", "3xx Redirect", "4xx Client-Fehler", "5xx Server-Fehler"]
    selected_status = st.sidebar.selectbox("Statuscodes", options=status_options, index=0)

    # Search filter
    search_query = st.sidebar.text_input(
        "Suche", placeholder="IP, Domain oder Pfad...", help="Filtert Requests nach IP-Adresse, Domain oder Pfad"
    )

    st.sidebar.divider()

    # Database info
    st.sidebar.subheader("Datenbank")
    db_info = cached_db_info()
    st.sidebar.metric("Einträge", format_number(db_info["total_rows"] or 0))
    st.sidebar.metric("Größe", db_info["table_size"] or "0 B")

    if db_info["oldest_record"]:
        st.sidebar.caption(f"Ältester: {get_relative_time(db_info['oldest_record'])}")
    if db_info["newest_record"]:
        st.sidebar.caption(f"Neuester: {get_relative_time(db_info['newest_record'])}")

    st.sidebar.divider()

    # Sync status
    st.sidebar.subheader("Sync-Status")
    newest = get_newest_timestamp()
    if newest:
        st.sidebar.caption(f"Letzte Daten: {get_relative_time(newest)}")
        time_since_sync = datetime.now(newest.tzinfo) - newest
        if time_since_sync.total_seconds() < 300:
            st.sidebar.success("● Aktuell")
        elif time_since_sync.total_seconds() < 3600:
            st.sidebar.info("● Vor wenigen Minuten")
        else:
            st.sidebar.warning("● Veraltet")
    else:
        st.sidebar.caption("Keine Daten vorhanden")

    if st.sidebar.button("Jetzt synchronisieren"):
        with st.sidebar.status("Synchronisiere..."):
            inserted = sync_logs_callback()
        st.sidebar.success(f"{inserted} neue Einträge")

    st.sidebar.divider()

    # Auto-refresh
    st.sidebar.subheader("Auto-Refresh")
    auto_refresh = st.sidebar.toggle("Aktiviert", value=False)
    refresh_interval = st.sidebar.selectbox(
        "Intervall",
        options=[30, 60, 120, 300],
        format_func=lambda x: f"{x} Sekunden" if x < 60 else f"{x // 60} Minuten",
        index=1,
        disabled=not auto_refresh,
    )

    st.sidebar.divider()

    # Maintenance
    st.sidebar.subheader("Wartung")
    st.sidebar.caption(f"Aufbewahrung: {app_config.retention_days} Tage")
    if db_info["oldest_record"]:
        oldest = db_info["oldest_record"]
        cleanup_date = oldest + timedelta(days=app_config.retention_days)
        st.sidebar.caption(f"Nächste Bereinigung: {cleanup_date.strftime('%d.%m.%Y')}")
    if st.sidebar.button("Alte Daten bereinigen"):
        deleted = cleanup_old_data_callback()
        st.sidebar.success(f"{deleted} alte Einträge gelöscht")

    return selected_hosts, start_date, end_date, auto_refresh, refresh_interval, search_query, selected_status
