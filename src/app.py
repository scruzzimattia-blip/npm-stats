"""Main Streamlit application for NPM Monitor."""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

import pandas as pd
import streamlit as st

from .config import app_config
from .database import (
    init_database,
    insert_traffic_batch,
    cleanup_old_data,
    get_distinct_hosts,
    get_traffic_stats,
    get_database_info,
    health_check,
    load_traffic_df,
)
from .log_parser import parse_all_logs, init_geoip
from .utils import (
    setup_logging,
    format_number,
    calculate_error_rate,
    get_time_ranges,
    parse_user_agent,
    get_status_category,
    df_to_csv,
    get_relative_time,
)

logger = logging.getLogger(__name__)


def sync_logs() -> int:
    """Synchronize logs to database."""
    init_database()
    rows = parse_all_logs()
    inserted = insert_traffic_batch(rows)
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


def render_sidebar() -> tuple:
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
    hosts = _cached_hosts()
    selected_hosts = st.sidebar.multiselect(
        "Domains",
        options=hosts,
        default=hosts,
        help="Wähle die Domains aus, die angezeigt werden sollen"
    )

    st.sidebar.divider()

    # Database info
    st.sidebar.subheader("Datenbank")
    db_info = _cached_db_info()
    st.sidebar.metric("Einträge", format_number(db_info["total_rows"] or 0))
    st.sidebar.metric("Größe", db_info["table_size"] or "0 B")

    if db_info["oldest_record"]:
        st.sidebar.caption(f"Ältester: {get_relative_time(db_info['oldest_record'])}")
    if db_info["newest_record"]:
        st.sidebar.caption(f"Neuester: {get_relative_time(db_info['newest_record'])}")

    st.sidebar.divider()

    # Maintenance
    st.sidebar.subheader("Wartung")
    if st.sidebar.button("Alte Daten bereinigen"):
        deleted = cleanup_old_data()
        st.sidebar.success(f"{deleted} alte Einträge gelöscht")

    return selected_hosts, start_date, end_date


def render_metrics(df: pd.DataFrame) -> None:
    """Render key metrics."""
    if df.empty:
        return

    col1, col2, col3, col4, col5 = st.columns(5)

    total = len(df)
    unique_ips = df["remote_addr"].nunique()
    errors = len(df[df["status"] >= 400])
    err_rate = calculate_error_rate(total, errors)
    distinct_hosts = df["host"].nunique()
    distinct_countries = df["country_code"].nunique() if "country_code" in df.columns else 0

    col1.metric("Requests", format_number(total))
    col2.metric("Unique IPs", format_number(unique_ips))
    col3.metric("Fehlerrate", f"{err_rate:.1f}%")
    col4.metric("Domains", format_number(distinct_hosts))
    col5.metric("Länder", format_number(distinct_countries))


def render_charts(df: pd.DataFrame) -> None:
    """Render traffic charts."""
    if df.empty:
        return

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Requests pro Stunde")
        time_df = df.set_index("time").resample("1h").size().rename("Requests")
        st.area_chart(time_df, width="stretch")

    with col2:
        st.subheader("Statuscodes")
        status_counts = df["status"].value_counts().sort_index()
        st.bar_chart(status_counts)

    st.divider()

    # Status categories
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Status-Kategorien")
        df["status_category"] = df["status"].apply(get_status_category)
        cat_counts = df["status_category"].value_counts()
        st.bar_chart(cat_counts)

    with col2:
        st.subheader("Top 10 Domains")
        top_hosts = df["host"].value_counts().head(10).reset_index()
        top_hosts.columns = ["Domain", "Requests"]
        st.dataframe(top_hosts, width="stretch", hide_index=True)

    with col3:
        st.subheader("Top 10 Pfade")
        top_paths = df["path"].value_counts().head(10).reset_index()
        top_paths.columns = ["Pfad", "Requests"]
        st.dataframe(top_paths, width="stretch", hide_index=True)


def render_geo_analysis(df: pd.DataFrame) -> None:
    """Render geographic analysis if GeoIP data available."""
    if df.empty or "country_code" not in df.columns:
        return

    # Check if we have any geo data
    if df["country_code"].isna().all():
        return

    st.divider()
    st.subheader("Geografische Analyse")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Top 10 Länder**")
        country_counts = df["country_code"].value_counts().head(10).reset_index()
        country_counts.columns = ["Land", "Requests"]
        st.dataframe(country_counts, width="stretch", hide_index=True)

    with col2:
        if "city" in df.columns and not df["city"].isna().all():
            st.write("**Top 10 Städte**")
            city_counts = df["city"].dropna().value_counts().head(10).reset_index()
            city_counts.columns = ["Stadt", "Requests"]
            st.dataframe(city_counts, width="stretch", hide_index=True)


def render_user_agent_analysis(df: pd.DataFrame) -> None:
    """Render user agent analysis."""
    if df.empty or "user_agent" not in df.columns:
        return

    st.divider()
    st.subheader("Browser & Geräte")

    # Parse user agents (only unique values, then map back)
    unique_uas = df["user_agent"].unique()
    ua_map = {ua: parse_user_agent(ua) for ua in unique_uas}
    ua_data = df["user_agent"].map(ua_map).apply(pd.Series)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Browser**")
        browser_counts = ua_data["browser"].value_counts().reset_index()
        browser_counts.columns = ["Browser", "Requests"]
        st.dataframe(browser_counts, width="stretch", hide_index=True)

    with col2:
        st.write("**Betriebssystem**")
        os_counts = ua_data["os"].value_counts().reset_index()
        os_counts.columns = ["OS", "Requests"]
        st.dataframe(os_counts, width="stretch", hide_index=True)

    with col3:
        st.write("**Gerätetyp**")
        device_counts = ua_data["device"].value_counts().reset_index()
        device_counts.columns = ["Gerät", "Requests"]
        st.dataframe(device_counts, width="stretch", hide_index=True)


def render_request_log(df: pd.DataFrame) -> None:
    """Render recent requests with export option."""
    if df.empty:
        return

    st.divider()
    st.subheader("Request Log")

    # Export button
    col1, col2 = st.columns([4, 1])
    with col2:
        csv = df_to_csv(df)
        st.download_button(
            label="CSV Export",
            data=csv,
            file_name=f"npm_traffic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

    # Display table
    display_cols = ["time", "host", "method", "path", "status", "remote_addr"]
    if "country_code" in df.columns and not df["country_code"].isna().all():
        display_cols.append("country_code")

    st.dataframe(
        df[display_cols].head(1000),
        width="stretch",
        hide_index=True,
    )

    if len(df) > 1000:
        st.caption(f"Zeige 1000 von {format_number(len(df))} Einträgen")


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

    # Header with sync button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🌐 NPM Traffic Monitor")
    with col2:
        if st.button("🔄 Sync", width="stretch"):
            with st.spinner("Synchronisiere..."):
                new_rows = sync_logs()
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
            if new_rows > 0:
                st.toast(f"{new_rows} neue Einträge", icon="✅")

    # Sidebar filters
    selected_hosts, start_date, end_date = render_sidebar()

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

    if df.empty:
        st.info("Keine Daten für den ausgewählten Filter gefunden.")
        return

    # Render dashboard
    render_metrics(df)
    st.divider()
    render_charts(df)
    render_geo_analysis(df)
    render_user_agent_analysis(df)
    render_request_log(df)


if __name__ == "__main__":
    main()
