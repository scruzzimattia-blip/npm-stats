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
from src.database import get_traffic_count, get_latest_logs, get_traffic_spike_metrics
from src.utils.reports import generate_pdf_report
from src.utils.health import check_npm_status
from src.config import app_config

def main():
    init_page("Dashboard", "📊")
    st.title("📊 Traffic Übersicht")
    
    handle_sync_button()
    
    selected_hosts, start_date, end_date, auto_refresh, refresh_interval, search_query, selected_status = render_common_sidebar()

    if not selected_hosts:
        st.warning("Bitte wähle mindestens eine Domain aus.")
        st.stop()

    # Anomaly Detection
    if app_config.enable_anomaly_detection:
        spike_info = get_traffic_spike_metrics(hosts=selected_hosts)
        if spike_info["is_spike"]:
            st.error(
                f"⚠️ **TRAFFIC ANOMALIE ERKANNT!**\n\n"
                f"Anfragerate: {spike_info['current_rate']} req/min (Normal: {spike_info['baseline_rate']} req/min)\n"
                f"Anzahl Anfragen (5m): {spike_info['recent_count']}"
            )

    # System Status
    with st.expander("🛠️ System Status", expanded=False):
        status = check_npm_status()
        cols = st.columns(3)
        port_labels = {80: "HTTP (80)", 443: "HTTPS (443)", 81: "Admin (81)"}
        for i, port in enumerate((80, 443, 81)):
            is_up = status.get(port, False)
            color = "🟢 Online" if is_up else "🔴 Offline"
            cols[i].metric(port_labels[port], color)

    # Auto-sync on first load
    if "synced" not in st.session_state:
        sync_logs()
        st.session_state.synced = True

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

    tab1, tab2, tab3 = st.tabs(["📊 Übersicht", "🔴 Live Logs", "🔄 NPM Hosts"])
    
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

    with tab3:
        st.subheader("Nginx Proxy Manager Hosts & Uptime")
        from src.utils.npm_sync import fetch_npm_proxy_hosts
        from src.database import get_all_host_health
        
        npm_hosts = fetch_npm_proxy_hosts()
        health_data = {h['host']: h for h in get_all_host_health()}
        
        if npm_hosts:
            display_data = []
            for h in npm_hosts:
                domain = h["domains"][0] if h["domains"] else "Unknown"
                health = health_data.get(domain, {})
                
                status_str = "🟢 UP" if health.get('is_up') else "🔴 DOWN"
                if not health: status_str = "⚪ NO DATA"
                
                ssl_info = "N/A"
                if h["ssl"]:
                    expiry = health.get('ssl_expiry')
                    if expiry:
                        days_left = (expiry - datetime.now(timezone.utc)).days
                        ssl_info = f"🔒 {days_left} Tage"
                    else:
                        ssl_info = "🔒 Prüfe..."
                
                display_data.append({
                    "Status": status_str,
                    "Domain": domain,
                    "Forward To": h["forward"],
                    "SSL": ssl_info,
                    "Response": f"{health.get('response_time', 0) * 1000:.0f}ms" if health.get('response_time') else "-",
                    "Letzter Check": health.get('last_check').strftime('%H:%M') if health.get('last_check') else "-"
                })
            
            st.dataframe(display_data, use_container_width=True, hide_index=True)
        else:
            st.info("Keine Hosts gefunden oder NPM Datenbank nicht konfiguriert.")

if __name__ == "__main__":
    main()
