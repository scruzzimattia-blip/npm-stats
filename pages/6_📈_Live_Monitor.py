import streamlit as st
import pandas as pd
import time
from datetime import datetime, timezone
import requests
from src.ui_utils import init_page, render_common_sidebar

def fetch_recent_traffic():
    """Fetch recent traffic from our new API."""
    try:
        response = requests.get("http://npm-api:8001/traffic/recent?limit=50", timeout=5)
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
                        if val >= 500: return 'background-color: #ff4b4b; color: white'
                        if val >= 400: return 'background-color: #ffa500; color: black'
                        if val >= 300: return 'background-color: #3182bd; color: white'
                        return 'background-color: #28a745; color: white'
                    
                    styled_df = df[['time', 'remote_addr', 'method', 'host', 'path', 'status']].style.applymap(
                        color_status, subset=['status']
                    )
                    log_container.dataframe(styled_df, use_container_width=True, hide_index=True)
                
                time.sleep(2)
        else:
            df = fetch_recent_traffic()
            if not df.empty:
                st.dataframe(df[['time', 'remote_addr', 'method', 'host', 'path', 'status']], use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Verbindungs-Graph")
        st.info("Visualisierung der Beziehungen zwischen IPs, Hosts und Pfaden.")
        
        df = fetch_recent_traffic()
        if not df.empty:
            import graphviz
            dot = graphviz.Digraph()
            dot.attr(rankdir='LR', size='10,10')
            
            # Limit to last 20 unique connections for clarity
            for _, row in df.head(20).iterrows():
                ip = row['remote_addr']
                host = row['host']
                path = row['path']
                
                dot.node(ip, ip, shape='ellipse', color='red' if row['status'] >= 400 else 'blue')
                dot.node(host, host, shape='box')
                dot.edge(ip, host, label=row['method'])
                dot.edge(host, path, label=str(row['status']))
            
            st.graphviz_chart(dot)

if __name__ == "__main__":
    main()
