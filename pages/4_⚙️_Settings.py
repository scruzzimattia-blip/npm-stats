import streamlit as st
import os
from src.ui_utils import init_page, render_common_sidebar, _cached_db_info
from src.config import app_config
from src.database import update_setting

def main():
    init_page("Einstellungen", "⚙️")
    st.title("⚙️ Systemeinstellungen")
    
    render_common_sidebar()

    # Create tabs for different setting categories
    tab_gen, tab_sec, tab_notify, tab_db = st.tabs([
        "🏠 Allgemein", 
        "🛡️ Sicherheit & Blocking", 
        "🔔 Benachrichtigungen",
        "📊 Datenbank & Cache"
    ])

    with tab_gen:
        st.subheader("Allgemeine Konfiguration")
        with st.form("general_settings"):
            retention = st.number_input(
                "Daten-Retention (Tage)", 
                min_value=1, max_value=365, 
                value=app_config.retention_days,
                help="Wie lange sollen Traffic-Logs in der Datenbank gespeichert werden?"
            )
            
            enable_geoip = st.checkbox(
                "GeoIP Aktivieren", 
                value=app_config.enable_geoip,
                help="Erfordert MaxMind Datenbank im geoip Verzeichnis."
            )
            
            if st.form_submit_button("Allgemein Speichern"):
                update_setting("retention_days", retention)
                update_setting("enable_geoip", enable_geoip)
                st.success("Allgemeine Einstellungen gespeichert!")
                st.rerun()

    with tab_sec:
        st.subheader("Sicherheits-Schwellwerte")
        st.info("Diese Werte bestimmen, wann eine IP automatisch gesperrt wird (innerhalb von 5 Min).")
        with st.form("security_settings"):
            col1, col2 = st.columns(2)
            with col1:
                max_404 = st.number_input("Max. 404 Fehler", value=app_config.max_404_errors)
                max_403 = st.number_input("Max. 403 Fehler", value=app_config.max_403_errors)
                max_5xx = st.number_input("Max. 5xx Fehler", value=app_config.max_5xx_errors)
            with col2:
                max_failed = st.number_input("Gesamt fehlgeschlagene Requests", value=app_config.max_failed_requests)
                max_suspicious = st.number_input("Max. verdächtige Pfade", value=app_config.max_suspicious_paths)
                block_dur = st.number_input("Sperrdauer (Sekunden)", value=app_config.block_duration, step=60)
            
            suspicious_paths = st.text_area(
                "Verdächtige Pfade (kommagetrennt)", 
                value=",".join(app_config.suspicious_paths),
                help="Pfade, die sofort als verdächtig markiert werden (z.B. /wp-admin)"
            )
            
            enable_blocking = st.checkbox("Automatisches Blocking Aktiv", value=app_config.enable_blocking)
            
            if st.form_submit_button("Sicherheit Speichern"):
                update_setting("max_404_errors", max_404)
                update_setting("max_403_errors", max_403)
                update_setting("max_5xx_errors", max_5xx)
                update_setting("max_failed_requests", max_failed)
                update_setting("max_suspicious_paths", max_suspicious)
                update_setting("block_duration", block_dur)
                update_setting("suspicious_paths", suspicious_paths)
                update_setting("enable_blocking", enable_blocking)
                st.success("Sicherheitseinstellungen gespeichert!")
                st.rerun()

    with tab_notify:
        st.subheader("Alerting Konfiguration")
        with st.form("notification_settings"):
            webhook = st.text_input(
                "Webhook URL", 
                value=app_config.webhook_url,
                placeholder="https://discord.com/api/webhooks/...",
                help="Discord, Slack oder kompatible Webhooks"
            )
            notify = st.checkbox("Benachrichtigung bei Blockierung senden", value=app_config.notify_on_block)
            
            if st.form_submit_button("Alerting Speichern"):
                update_setting("webhook_url", webhook)
                update_setting("notify_on_block", notify)
                st.success("Alerting-Einstellungen gespeichert!")
                st.rerun()

    with tab_db:
        st.subheader("Datenbank Status")
        db_info = _cached_db_info()
        
        stats_col1, stats_col2, stats_col3 = st.columns(3)
        stats_col1.metric("Gesamt Einträge", db_info["total_rows"])
        stats_col2.metric("Aktive Sperren", db_info["blocked_count"])
        stats_col3.metric("DB Größe", db_info["table_size"])
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ UI-Cache leeren", use_container_width=True):
                st.cache_data.clear()
                st.toast("Cache erfolgreich geleert", icon="✅")
        with col2:
            if st.button("🧹 Alte Daten jetzt bereinigen", use_container_width=True):
                from src.database import cleanup_old_data
                deleted = cleanup_old_data()
                st.success(f"{deleted} alte Einträge gelöscht.")

if __name__ == "__main__":
    main()
