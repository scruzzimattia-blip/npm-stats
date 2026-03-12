import streamlit as st
import pandas as pd
from datetime import datetime, time as dt_time, timezone
from streamlit_autorefresh import st_autorefresh
from src.ui_utils import (
    init_page, 
    handle_sync_button, 
    render_common_sidebar, 
    load_traffic_data, 
    _cached_hourly_summary, 
    _cached_top_ips,
    _cached_traffic_metrics,
    sync_logs
)
from src.components import (
    render_metrics,
    render_charts,
    render_top_ips,
    render_error_paths,
    render_request_log
)
from src.database import get_traffic_count, get_latest_logs
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
    metrics = _cached_traffic_metrics(hosts=selected_hosts, start_date=start_date, end_date=end_date)
    df = load_traffic_data(
        hosts=selected_hosts,
        start_date=start_date,
        end_date=end_date,
        limit=1000
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

    render_metrics(metrics)
    st.divider()
    
    hourly_summary = _cached_hourly_summary(hosts=selected_hosts, start_date=start_date, end_date=end_date)
    top_ips_summary = _cached_top_ips(hosts=selected_hosts, start_date=start_date, end_date=end_date)

    tab1, tab2 = st.tabs(["📊 Übersicht", "🔴 Live Logs"])
    
    with tab1:
        render_charts(df, hourly_summary)
        render_top_ips(df, top_ips_summary)
        render_error_paths(df)
        render_request_log(df)
        
    with tab2:
        col_l1, col_l2 = st.columns([1, 4])
        with col_l1:
            auto_refresh_live = st.toggle("Auto-Refresh (5s)", value=False, key="live_log_toggle")
            
        if auto_refresh_live:
            st_autorefresh(interval=5000, limit=None, key="live_log_refresh")
            
        live_df = get_latest_logs(limit=20)
        if not live_df.empty:
            display_df = live_df.copy()
            if "time" in display_df.columns:
                display_df["time"] = display_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Select columns to show
            cols_to_show = ["time", "host", "method", "path", "status", "remote_addr"]
            if "country_code" in display_df.columns:
                cols_to_show.append("country_code")
                
            st.dataframe(
                display_df[cols_to_show],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Keine Live-Logs verfügbar.")

if __name__ == "__main__":
    main()
