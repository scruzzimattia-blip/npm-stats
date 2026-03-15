"""Tables and metric components for Streamlit application."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import streamlit as st

from ..utils import (
    calculate_error_rate,
    df_to_csv,
    df_to_json,
    format_bytes,
    format_number,
)


def render_metrics(data: Union[pd.DataFrame, Dict[str, Any]]) -> None:
    """Render key metrics."""
    if isinstance(data, pd.DataFrame):
        if data.empty:
            return
        total = len(data)
        unique_ips = data["remote_addr"].nunique()
        errors = len(data[data["status"] >= 400])
        err_rate = calculate_error_rate(total, errors)
        distinct_hosts = data["host"].nunique()
        distinct_countries = data["country_code"].nunique() if "country_code" in data.columns else 0
        total_bytes = data["response_length"].sum() if "response_length" in data.columns else 0
    else:
        # Dictionary from DB aggregation
        total = data.get("total_requests", 0)
        unique_ips = data.get("unique_ips", 0)
        errors = data.get("error_count", 0)
        err_rate = calculate_error_rate(total, errors)
        # These are not in the fast metrics query, fallback to 0 or estimates
        distinct_hosts = 0 
        distinct_countries = 0
        total_bytes = data.get("total_bytes", 0)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Requests", format_number(total))
    col2.metric("Unique IPs", format_number(unique_ips))
    col3.metric("Fehlerrate", f"{err_rate:.1f}%")
    col4.metric("Bandbreite", format_bytes(total_bytes))
    
    if isinstance(data, pd.DataFrame):
        col5.metric("Domains", format_number(distinct_hosts))
        col6.metric("Länder", format_number(distinct_countries))


def render_geo_summary(df: pd.DataFrame, geo_stats: Optional[Dict[str, pd.DataFrame]] = None) -> None:
    """Render a detailed table of geographic traffic distribution."""
    if geo_stats and not geo_stats.get("countries", pd.DataFrame()).empty:
        # Use optimized DB aggregation
        country_df = geo_stats["countries"]
        city_df = geo_stats.get("cities", pd.DataFrame())

        st.subheader("📊 Top Länder nach Traffic")
        display_df = country_df.copy()
        display_df.columns = ["Land", "Requests", "Fehler"]
        display_df["Eindeutige IPs"] = "N/A" # We skipped COUNT(DISTINCT) for performance, show N/A or calculate differently
        display_df["Fehlerrate"] = (display_df["Fehler"] / display_df["Requests"] * 100).round(1).astype(str) + "%"

        st.dataframe(
            display_df[["Land", "Requests", "Eindeutige IPs", "Fehlerrate"]].head(15),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("🏙️ Top Städte")
        if not city_df.empty:
            city_display = city_df.copy()
            city_display.columns = ["Stadt", "Requests"]
            city_display["Land"] = "N/A" # Simplified for performance
            st.dataframe(city_display[["Stadt", "Land", "Requests"]].head(15), use_container_width=True, hide_index=True)

    else:
        # Fallback to pandas aggregation if no geo_stats provided
        if df.empty or "country_code" not in df.columns:
            return

        st.subheader("📊 Top Länder nach Traffic")

        # Calculate stats per country
        geo_agg = df.groupby("country_code").agg({
            "remote_addr": ["count", "nunique"],
            "status": lambda x: (x >= 400).sum()
        }).reset_index()

        geo_agg.columns = ["Land", "Requests", "Eindeutige IPs", "Fehler"]
        geo_agg = geo_agg.sort_values("Requests", ascending=False).head(15)

        # Add error rate
        geo_agg["Fehlerrate"] = (geo_agg["Fehler"] / geo_agg["Requests"] * 100).round(1).astype(str) + "%"

        st.dataframe(
            geo_agg[["Land", "Requests", "Eindeutige IPs", "Fehlerrate"]],
            use_container_width=True,
            hide_index=True
        )

        st.subheader("🏙️ Top Städte")
        city_stats = df.groupby(["city", "country_code"]).size().reset_index(name="Requests")
        city_stats = city_stats.sort_values("Requests", ascending=False).head(15)
        city_stats.columns = ["Stadt", "Land", "Requests"]

        st.dataframe(city_stats, use_container_width=True, hide_index=True)

def render_top_ips(df: pd.DataFrame, top_ips_summary: pd.DataFrame = None) -> None:
    """Render top IP addresses analysis with optimized summary."""
    if df.empty:
        return

    st.divider()
    with st.expander("Top IPs", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Top 10 IPs nach Requests**")
            # Use optimized summary if available
            if top_ips_summary is not None and not top_ips_summary.empty:
                top_ips = top_ips_summary.head(10)[["remote_addr", "request_count"]].copy()
                top_ips.columns = ["IP-Adresse", "Requests"]
            else:
                top_ips = df["remote_addr"].value_counts().head(10).reset_index()
                top_ips.columns = ["IP-Adresse", "Requests"]
            st.dataframe(top_ips, width="stretch", hide_index=True)

        with col2:
            st.write("**Top 10 IPs nach Fehlern**")
            # Use optimized summary if available
            if top_ips_summary is not None and not top_ips_summary.empty:
                error_ips = top_ips_summary[top_ips_summary["error_count"] > 0].head(10)
                if not error_ips.empty:
                    top_error_ips = error_ips[["remote_addr", "error_count"]].copy()
                    top_error_ips.columns = ["IP-Adresse", "Fehler"]
                    st.dataframe(top_error_ips, width="stretch", hide_index=True)
                else:
                    st.info("Keine Fehler im ausgewählten Zeitraum.")
            else:
                error_df = df[df["status"] >= 400]
                if not error_df.empty:
                    top_error_ips = error_df["remote_addr"].value_counts().head(10).reset_index()
                    top_error_ips.columns = ["IP-Adresse", "Fehler"]
                    st.dataframe(top_error_ips, width="stretch", hide_index=True)
                else:
                    st.info("Keine Fehler im ausgewählten Zeitraum.")


def render_request_log(df: pd.DataFrame) -> None:
    """Render recent requests with pagination and export options."""
    if df.empty:
        return

    st.divider()
    with st.expander("Request Log", expanded=True):
        # Export buttons and pagination controls
        col1, col2, col3 = st.columns([2, 1, 1])

        # Pagination settings
        page_size = 100
        total_rows = len(df)
        total_pages = max(1, (total_rows + page_size - 1) // page_size)

        with col1:
            current_page = st.number_input(
                "Seite",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
                help=f"Seite 1-{total_pages} ({format_number(total_rows)} Einträge)",
            )

        with col2:
            csv = df_to_csv(df)
            st.download_button(
                label="CSV Export",
                data=csv,
                file_name=f"npm_traffic_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

        with col3:
            json_data = df_to_json(df)
            st.download_button(
                label="JSON Export",
                data=json_data,
                file_name=f"npm_traffic_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

        # Display table with pagination
        display_cols = ["time", "host", "method", "path", "status", "remote_addr"]
        if "country_code" in df.columns and not df["country_code"].isna().all():
            display_cols.append("country_code")

        start_idx = (current_page - 1) * page_size
        end_idx = min(start_idx + page_size, total_rows)

        st.dataframe(
            df[display_cols].iloc[start_idx:end_idx],
            width="stretch",
            hide_index=True,
        )

        st.caption(f"Zeige {start_idx + 1}-{end_idx} von {format_number(total_rows)} Einträgen")


def render_npm_hosts_status() -> None:
    """Render Nginx Proxy Manager hosts and their health status."""
    from ..utils.npm_sync import fetch_npm_proxy_hosts, check_all_hosts_health
    from ..database import get_all_host_health
    from ..utils.health import check_npm_status
    
    st.subheader("🛠️ NPM System Status")
    status = check_npm_status()
    cols = st.columns(3)
    port_labels = {80: "HTTP (80)", 443: "HTTPS (443)", 81: "Admin (81)"}
    for i, port in enumerate((80, 443, 81)):
        is_up = status.get(port, False)
        color = "🟢 Online" if is_up else "🔴 Offline"
        cols[i].metric(port_labels[port], color)
    
    st.divider()
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("🌐 NPM Hosts & Uptime")
    with col2:
        if st.button("🔄 Status aktualisieren", use_container_width=True):
            with st.spinner("Prüfe Hosts..."):
                check_all_hosts_health()
                st.cache_data.clear()
                st.success("Status aktualisiert!")
                st.rerun()

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

