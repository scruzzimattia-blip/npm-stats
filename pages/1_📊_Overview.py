import streamlit as st
import pandas as pd
from datetime import datetime, time as dt_time, timezone
from src.ui_utils import (
    init_page, 
    handle_sync_button, 
    render_common_sidebar, 
    load_traffic_data, 
    _cached_hourly_summary, 
    _cached_top_ips,
    sync_logs
)
from src.components import (
    render_metrics,
    render_charts,
    render_top_ips,
    render_error_paths,
    render_request_log
)
from src.database import get_traffic_count
from src.utils.reports import generate_pdf_report

def main():
    init_page("Dashboard", "📊")
    st.title("📊 Traffic Übersicht")
    
    handle_sync_button()
    
    # Auto-sync on first load
    if "synced" not in st.session_state:
        sync_logs()
        st.session_state.synced = True

    selected_hosts, start_date, end_date, auto_refresh, refresh_interval, search_query, selected_status = render_common_sidebar()

    if not selected_hosts:
        st.warning("Bitte wähle mindestens eine Domain aus.")
        st.stop()

    # Load data
    total_count = get_traffic_count(hosts=selected_hosts, start_date=start_date, end_date=end_date)
    df = load_traffic_data(
        hosts=tuple(selected_hosts),
        start_date=start_date,
        end_date=end_date,
        limit=10000
    )

    # PDF Export in Sidebar
    st.sidebar.subheader("Export")
    if st.sidebar.button("📄 Export als PDF", use_container_width=True):
        pdf_data = generate_pdf_report(df, f"Traffic Report {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
        if pdf_data:
            st.sidebar.download_button(
                "⬇️ PDF Herunterladen",
                data=pdf_data,
                file_name=f"npm_monitor_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    render_metrics(df)
    st.divider()
    
    hourly_summary = _cached_hourly_summary(hosts=tuple(selected_hosts), start_date=start_date, end_date=end_date)
    top_ips_summary = _cached_top_ips(hosts=tuple(selected_hosts), start_date=start_date, end_date=end_date)

    render_charts(df, hourly_summary)
    render_top_ips(df, top_ips_summary)
    render_error_paths(df)
    render_request_log(df)

if __name__ == "__main__":
    main()
