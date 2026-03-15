"""Charts components for Streamlit application."""

import pandas as pd
import streamlit as st

from ..utils import (
    calculate_percentiles,
    format_bytes,
    format_number,
    get_status_category,
    parse_user_agent,
)


import altair as alt

def render_charts(df: pd.DataFrame, hourly_summary: pd.DataFrame = None) -> None:
    """Render traffic charts with optimized hourly summary."""
    if df.empty:
        return

    granularity_options = {"5 Minuten": "5min", "15 Minuten": "15min", "1 Stunde": "1h", "1 Tag": "1D"}

    col1, col2 = st.columns([2, 1])

    with col1:
        gcol1, gcol2 = st.columns([3, 1])
        with gcol1:
            st.subheader("Requests über Zeit (mit Anomalie-Erkennung)")
        with gcol2:
            selected_granularity = st.selectbox(
                "Granularität",
                options=list(granularity_options.keys()),
                index=2,
                label_visibility="collapsed",
            )
        
        # Prepare Data
        if hourly_summary is not None and not hourly_summary.empty and selected_granularity == "1 Stunde":
            time_df = hourly_summary.set_index("hour")["request_count"].reset_index()
            time_df.columns = ["time", "Requests"]
        else:
            bucket = granularity_options[selected_granularity]
            time_df = df.set_index("time").resample(bucket).size().reset_index()
            time_df.columns = ["time", "Requests"]

        # Simple Anomaly Detection (Z-Score)
        if len(time_df) > 3:
            mean = time_df["Requests"].mean()
            std = time_df["Requests"].std()
            time_df["Anomaly"] = time_df["Requests"] > (mean + (3 * std))
        else:
            time_df["Anomaly"] = False

        # Build Altair Chart
        base = alt.Chart(time_df).encode(x=alt.X('time:T', title='Zeit'))
        
        area = base.mark_area(opacity=0.5, color='#3182bd').encode(
            y=alt.Y('Requests:Q', title='Requests')
        )
        
        points = base.mark_circle(size=60).encode(
            y='Requests:Q',
            color=alt.condition(
                alt.datum.Anomaly,
                alt.value('red'),     # Outliers are red
                alt.value('transparent') # Normal points are invisible
            ),
            tooltip=['time', 'Requests', 'Anomaly']
        )
        
        st.altair_chart(area + points, use_container_width=True)

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


def render_error_paths(df: pd.DataFrame) -> None:
    """Render top error-producing paths."""
    if df.empty:
        return

    error_df = df[df["status"] >= 400]
    if error_df.empty:
        return

    st.divider()
    with st.expander("Fehler-Analyse", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Top 10 Fehler-Pfade**")
            error_paths = error_df.groupby(["host", "path", "status"]).size().reset_index(name="Anzahl")
            error_paths = error_paths.sort_values("Anzahl", ascending=False).head(10)
            error_paths.columns = ["Domain", "Pfad", "Status", "Anzahl"]
            st.dataframe(error_paths, width="stretch", hide_index=True)

        with col2:
            st.write("**Fehler nach Statuscode**")
            error_status = error_df["status"].value_counts().sort_index().reset_index()
            error_status.columns = ["Statuscode", "Anzahl"]
            st.dataframe(error_status, width="stretch", hide_index=True)


def render_bandwidth_analysis(df: pd.DataFrame) -> None:
    """Render bandwidth analysis."""
    if df.empty or "response_length" not in df.columns:
        return

    st.divider()
    with st.expander("Bandbreiten-Analyse", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Datenvolumen pro Domain**")
            bw_by_host = df.groupby("host")["response_length"].sum().sort_values(ascending=False).head(10).reset_index()
            bw_by_host.columns = ["Domain", "Bytes"]
            bw_by_host["Volumen"] = bw_by_host["Bytes"].apply(format_bytes)
            st.dataframe(bw_by_host[["Domain", "Volumen"]], width="stretch", hide_index=True)

        with col2:
            st.write("**Datenvolumen pro Stunde**")
            bw_time = df.set_index("time")["response_length"].resample("1h").sum().rename("Bytes")
            st.area_chart(bw_time, width="stretch")

        # Response length percentiles
        st.write("**Response-Größen-Statistiken**")
        percentiles = calculate_percentiles(df["response_length"])
        pcol1, pcol2, pcol3 = st.columns(3)
        pcol1.metric("p50 (Median)", format_bytes(int(percentiles["p50"])))
        pcol2.metric("p95", format_bytes(int(percentiles["p95"])))
        pcol3.metric("p99", format_bytes(int(percentiles["p99"])))


def render_geo_analysis(df: pd.DataFrame, geo_stats: Optional[Dict[str, pd.DataFrame]] = None) -> None:
    """Render geographic analysis if GeoIP data available (optimized)."""
    if geo_stats and not geo_stats.get("countries", pd.DataFrame()).empty:
        st.divider()
        with st.expander("Geografische Analyse", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Top 10 Länder**")
                country_df = geo_stats["countries"].copy()
                country_df.columns = ["Land", "Requests", "Fehler"]
                st.dataframe(country_df[["Land", "Requests"]].head(10), width="stretch", hide_index=True)

            with col2:
                city_df = geo_stats.get("cities", pd.DataFrame())
                if not city_df.empty:
                    st.write("**Top 10 Städte**")
                    city_display = city_df.copy()
                    city_display.columns = ["Stadt", "Requests"]
                    st.dataframe(city_display.head(10), width="stretch", hide_index=True)
        return

    # Fallback to pandas aggregation
    if df.empty:
        return

    has_geo_data = "country_code" in df.columns and not df["country_code"].isna().all()

    if not has_geo_data:
        st.divider()
        st.subheader("Geografische Analyse")
        st.info(
            "GeoIP ist nicht konfiguriert. Für Länder- und Städteerkennung: "
            "1) Kostenlosen Account bei [MaxMind](https://www.maxmind.com/en/geolite2/signup) erstellen, "
            "2) MAXMIND_ACCOUNT_ID und MAXMIND_LICENSE_KEY in der .env setzen, "
            "3) Container neu starten und Sync ausführen."
        )
        return

    st.divider()
    with st.expander("Geografische Analyse", expanded=True):
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


def render_referer_analysis(df: pd.DataFrame) -> None:
    """Render referer analysis."""
    if df.empty or "referer" not in df.columns:
        return

    referer_df = df[df["referer"].notna() & (df["referer"] != "")]
    if referer_df.empty:
        return

    st.divider()
    with st.expander("Referer-Analyse", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Top 10 Referer**")
            top_refs = referer_df["referer"].value_counts().head(10).reset_index()
            top_refs.columns = ["Referer", "Requests"]
            st.dataframe(top_refs, width="stretch", hide_index=True)

        with col2:
            st.write("**Referer-Domains**")
            # Extract domain from referer URL
            domains = referer_df["referer"].str.extract(r"https?://([^/]+)", expand=False).dropna()
            if not domains.empty:
                top_domains = domains.value_counts().head(10).reset_index()
                top_domains.columns = ["Domain", "Requests"]
                st.dataframe(top_domains, width="stretch", hide_index=True)


def render_user_agent_analysis(df: pd.DataFrame) -> None:
    """Render user agent analysis."""
    if df.empty or "user_agent" not in df.columns:
        return

    st.divider()
    with st.expander("Browser & Geräte", expanded=True):
        # Parse user agents (only unique values, then map back)
        unique_uas = df["user_agent"].dropna().unique()
        ua_map = {ua: parse_user_agent(ua) for ua in unique_uas}
        
        # Create DataFrame more efficiently from list of dicts
        parsed_uas = [ua_map[ua] for ua in df["user_agent"].dropna()]
        ua_data = pd.DataFrame(parsed_uas)

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

        # Bot analysis
        if "is_bot" in ua_data.columns:
            bot_df = ua_data[ua_data["is_bot"]]
            if not bot_df.empty:
                st.write("**Bot-Traffic**")
                bot_count = len(bot_df)
                total_count = len(df)
                bot_percentage = (bot_count / total_count) * 100
                col1, col2 = st.columns(2)
                col1.metric("Bot-Requests", format_number(bot_count))
                col2.metric("Anteil", f"{bot_percentage:.1f}%")

                # Top bots
                st.write("**Top Bot-Kategorien**")
                category_counts = bot_df["bot_category"].value_counts().reset_index()
                category_counts.columns = ["Kategorie", "Requests"]
                st.dataframe(category_counts, width="stretch", hide_index=True)

                st.write("**Top Bot User-Agents**")
                bot_uas = df.loc[bot_df.index, "user_agent"].value_counts().head(10).reset_index()
                bot_uas.columns = ["User-Agent", "Requests"]
                st.dataframe(bot_uas, width="stretch", hide_index=True)
