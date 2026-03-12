import streamlit as st
import os
from src.ui_utils import init_page, render_common_sidebar, _cached_db_info
from src.config import app_config, db_config

def main():
    init_page("Einstellungen", "⚙️")
    st.title("⚙️ Systemeinstellungen")
    
    render_common_sidebar()

    st.subheader("Anwendungskonfiguration")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Allgemein**")
        st.write(f"- Log-Verzeichnis: `{app_config.log_dir}`")
        st.write(f"- Retention: `{app_config.retention_days} Tage`")
        st.write(f"- GeoIP Aktiv: `{app_config.enable_geoip}`")
        
    with col2:
        st.write("**Security**")
        st.write(f"- Blocking Aktiv: `{app_config.enable_blocking}`")
        st.write(f"- Sperrdauer: `{app_config.block_duration}s`")
        st.write(f"- Webhook gesetzt: `{'Ja' if app_config.webhook_url else 'Nein'}`")

    st.divider()
    
    st.subheader("Datenbank Status")
    db_info = _cached_db_info()
    
    stats_col1, stats_col2, stats_col3 = st.columns(3)
    stats_col1.metric("Gesamt Einträge", db_info["total_rows"])
    stats_col2.metric("Aktive Sperren", db_info["blocked_count"])
    stats_col3.metric("DB Größe", db_info["table_size"])
    
    st.divider()
    
    if st.button("🗑️ Cache leeren", use_container_width=True):
        st.cache_data.clear()
        st.toast("Cache erfolgreich geleert", icon="✅")

if __name__ == "__main__":
    main()
