from datetime import datetime, timezone

import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.components import (
    render_charts,
    render_error_paths,
    render_metrics,
    render_npm_hosts_status,
    render_request_log,
    render_top_ips,
)
from src.config import app_config
from src.database import get_attack_surface_stats, get_latest_logs, get_traffic_spike_metrics
from src.ui_utils import (
    _cached_hourly_summary,
    _cached_top_ips,
    _cached_traffic_metrics,
    handle_sync_button,
    init_page,
    load_traffic_data,
    render_common_sidebar,
)
from src.utils.reports import generate_pdf_report


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

    # Load data
    metrics = _cached_traffic_metrics(hosts=selected_hosts, start_date=start_date, end_date=end_date)

    if metrics["total_requests"] == 0:
        st.info("Keine Daten für den gewählten Zeitraum gefunden. Klicke oben rechts auf 🔄 Sync, um aktuelle Logs einzulesen.")
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

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Übersicht", "🔴 Live Logs", "🤖 KI Analyse", "🔄 NPM Hosts"])

    with tab1:
        render_charts(df, hourly_summary)

        # New Attack Surface Analytics
        st.subheader("🎯 Attack Surface Analytics")
        attack_stats = get_attack_surface_stats(limit=10)
        if not attack_stats.empty:
            col_a1, col_a2 = st.columns([2, 1])
            with col_a1:
                fig = px.bar(
                    attack_stats,
                    x="host",
                    y="attack_count",
                    color="unique_attackers",
                    title="Top angegriffene Hosts (Fehlerrate >= 400)",
                    labels={"attack_count": "Anzahl Angriffsversuche", "host": "Ziel-Host", "unique_attackers": "Eindeutige Angreifer"},
                    color_continuous_scale="Reds"
                )
                st.plotly_chart(fig, use_container_width=True)
            with col_a2:
                st.write("Detaillierte Host-Statistik")
                st.dataframe(attack_stats, hide_index=True, use_container_width=True)
        else:
            st.info("Keine Angriffsdaten für die aktuelle Auswahl verfügbar.")

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
        st.subheader("🤖 KI Sicherheits-Briefing")
        st.markdown("""
        Lasse dir eine KI-gestützte Analyse der Sicherheitslage der letzten 24 Stunden erstellen.
        Die KI analysiert Trends, blockierte IPs und verdächtige Muster.
        """)

        if st.button("✨ Bericht generieren", use_container_width=True):
            from src.utils.briefings import SecurityBriefing
            briefing = SecurityBriefing()
            with st.spinner("KI analysiert Daten..."):
                report = briefing.generate_daily_summary()
                if report:
                    st.markdown("---")
                    st.markdown(report)
                else:
                    st.error("Fehler beim Generieren des Berichts.")

    with tab4:
        render_npm_hosts_status()

if __name__ == "__main__":
    main()

