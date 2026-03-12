import streamlit as st
import pandas as pd
from src.ui_utils import (
    init_page, 
    handle_sync_button, 
    render_common_sidebar, 
    load_traffic_data,
    _cached_top_ips
)
from src.components import (
    render_geo_analysis,
    render_referer_analysis,
    render_user_agent_analysis
)
from src.components.maps import render_geo_map

def main():
    init_page("IP-Analyse", "🔎")
    st.title("🔎 IP & Geo-Analyse")
    
    handle_sync_button()
    
    selected_hosts, start_date, end_date, auto_refresh, refresh_interval, search_query, selected_status = render_common_sidebar()

    if not selected_hosts:
        st.warning("Bitte wähle mindestens eine Domain aus.")
        st.stop()

    # Load data with coordinates
    df = load_traffic_data(
        hosts=selected_hosts,
        start_date=start_date,
        end_date=end_date,
        limit=1000
    )

    # Geo Map
    render_geo_map(df)
    
    st.divider()
    
    # Other analyses
    col1, col2 = st.columns(2)
    with col1:
        render_geo_analysis(df)
    with col2:
        render_user_agent_analysis(df)
        
    st.divider()
    render_referer_analysis(df)

if __name__ == "__main__":
    main()
