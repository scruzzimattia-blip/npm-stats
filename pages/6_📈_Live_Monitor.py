import streamlit as st
import pandas as pd
import time
from datetime import datetime, timezone
import requests
import os
from src.ui_utils import init_page, render_common_sidebar

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8002")


def fetch_recent_traffic():
    """Fetch recent traffic from our new API."""
    try:
        response = requests.get(f"{API_BASE_URL}/traffic/recent?limit=50", timeout=5)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
    except Exception as e:
        st.error(f"Fehler beim Abrufen der API-Daten: {e}")
    return pd.DataFrame()


def main():
    init_page("Live Monitor", "📈")
    st.title("📈 Live Traffic & Network Graph")

    render_common_sidebar()

    tab1, tab2 = st.tabs(["📺 Live Log Tail", "🕸️ Network Graph"])

    with tab1:
        st.subheader("Echtzeit Log-Stream")
        log_container = st.empty()

        # Simple auto-refreshing log tail
        if st.checkbox("Live-Update aktivieren", value=True):
            while True:
                df = fetch_recent_traffic()
                if not df.empty:
                    # Color coding logic
                    def color_status(val):
                        if val >= 500:
                            return "background-color: #ff4b4b; color: white"
                        if val >= 400:
                            return "background-color: #ffa500; color: black"
                        if val >= 300:
                            return "background-color: #3182bd; color: white"
                        return "background-color: #28a745; color: white"

                    styled_df = df[["time", "remote_addr", "method", "host", "path", "status"]].style.applymap(
                        color_status, subset=["status"]
                    )
                    log_container.dataframe(styled_df, use_container_width=True, hide_index=True)

                time.sleep(2)
        else:
            df = fetch_recent_traffic()
            if not df.empty:
                st.dataframe(
                    df[["time", "remote_addr", "method", "host", "path", "status"]],
                    use_container_width=True,
                    hide_index=True,
                )

    with tab2:
        st.subheader("Verbindungs-Graph")
        st.info("Visualisierung der Beziehungen zwischen IPs, Hosts und Pfaden.")

        df = fetch_recent_traffic()
        if not df.empty:
            try:
                import graphviz

                dot = graphviz.Digraph(comment="NPM Traffic Graph")
                dot.attr(rankdir="LR", size="12,12")
                dot.attr("node", fontname="Arial", fontsize="10")

                # Use sets to track added nodes/edges to avoid duplicates
                added_nodes = set()

                # Limit to last 25 connections for better readability
                for _, row in df.head(25).iterrows():
                    ip = str(row["remote_addr"])
                    host = str(row["host"])
                    path = str(row["path"])
                    # Shorten long paths for display
                    display_path = (path[:30] + "..") if len(path) > 30 else path

                    # IP Node
                    if ip not in added_nodes:
                        dot.node(
                            ip,
                            ip,
                            shape="ellipse",
                            style="filled",
                            fillcolor="#ff4b4b" if row["status"] >= 400 else "#3182bd",
                            fontcolor="white",
                        )
                        added_nodes.add(ip)

                    # Host Node
                    if host not in added_nodes:
                        dot.node(host, host, shape="box", style="rounded,filled", fillcolor="#f0f2f6")
                        added_nodes.add(host)

                    # Path Node
                    path_id = f"{host}{path}"
                    if path_id not in added_nodes:
                        dot.node(path_id, display_path, shape="plaintext", fontsize="9")
                        added_nodes.add(path_id)

                    # Edges
                    dot.edge(ip, host, label=str(row["method"]))
                    dot.edge(host, path_id, label=str(row["status"]))

                st.graphviz_chart(dot, use_container_width=True)

            except ImportError:
                st.error("Python-Modul 'graphviz' fehlt. Bitte installiere es mit 'pip install graphviz'.")
            except Exception as e:
                st.error(f"Fehler bei der Graph-Erstellung: {e}")
                st.info(
                    "Hinweis: Stellen Sie sicher, dass 'graphviz' auch auf dem System (z.B. apt install graphviz) installiert ist."
                )


if __name__ == "__main__":
    main()
