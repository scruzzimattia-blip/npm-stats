"""Tables and metric components for Streamlit application."""

from datetime import datetime

import pandas as pd
import streamlit as st

from ..utils import (
    calculate_error_rate,
    df_to_csv,
    df_to_json,
    format_bytes,
    format_number,
)


def render_metrics(df: pd.DataFrame) -> None:
    """Render key metrics."""
    if df.empty:
        return

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    total = len(df)
    unique_ips = df["remote_addr"].nunique()
    errors = len(df[df["status"] >= 400])
    err_rate = calculate_error_rate(total, errors)
    distinct_hosts = df["host"].nunique()
    distinct_countries = df["country_code"].nunique() if "country_code" in df.columns else 0
    total_bytes = df["response_length"].sum() if "response_length" in df.columns else 0

    col1.metric("Requests", format_number(total))
    col2.metric("Unique IPs", format_number(unique_ips))
    col3.metric("Fehlerrate", f"{err_rate:.1f}%")
    col4.metric("Domains", format_number(distinct_hosts))
    col5.metric("Länder", format_number(distinct_countries))
    col6.metric("Bandbreite", format_bytes(total_bytes))


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
                file_name=f"npm_traffic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

        with col3:
            json_data = df_to_json(df)
            st.download_button(
                label="JSON Export",
                data=json_data,
                file_name=f"npm_traffic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
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
