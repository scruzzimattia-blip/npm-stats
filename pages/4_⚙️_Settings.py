import streamlit as st
import os
from src.ui_utils import init_page, render_common_sidebar, _cached_db_info
from src.config import app_config
from src.database import update_setting

def main():
    init_page("Einstellungen", "⚙️")
    st.title("⚙️ Systemeinstellungen")
    
    render_common_sidebar()

    tab_gen, tab_sec, tab_ai, tab_notify, tab_user, tab_db = st.tabs([
        "🏠 Allgemein", 
        "🛡️ Sicherheit & Blocking", 
        "🤖 AI & KI Analyse",
        "🔔 Benachrichtigungen",
        "👥 Benutzer",
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
        st.subheader("🛡️ Erweiterte Sicherheit")
        st.info("Diese Einstellungen erhöhen die Sicherheit deines Dashboards gegen Brute-Force und Scanner.")
        
        with st.form("security_hardening"):
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                allowed_nets = st.text_area(
                    "Erlaubte Netzwerke (IP-Allowlist, kommagetrennt)", 
                    value=",".join(app_config.allowed_networks),
                    help="Nur diese IPs dürfen auf das Dashboard zugreifen. Leer lassen für Zugriff von überall (nicht empfohlen)."
                )
            with col_h2:
                honey_dur = st.number_input(
                    "Honeypot Sperrdauer (Sekunden)", 
                    value=app_config.honey_pot_duration,
                    help="Dauer der Sperre, wenn ein Honeypot (z.B. /.env) aufgerufen wird. Standard: 31536000 (1 Jahr)."
                )
            
            enable_auth = st.checkbox("Authentifizierung Erzwingen", value=app_config.enable_auth)
            
            if st.form_submit_button("Härtung Speichern"):
                update_setting("allowed_networks", allowed_nets)
                update_setting("honey_pot_duration", honey_dur)
                update_setting("enable_auth", enable_auth)
                st.success("Sicherheitshärtung gespeichert!")
                st.rerun()

        st.divider()
        st.subheader("⚖️ Sicherheits-Schwellwerte")
            col1, col2 = st.columns(2)
            with col1:
                max_404 = st.number_input("Max. 404 Fehler", value=app_config.max_404_errors)
                max_403 = st.number_input("Max. 403 Fehler", value=app_config.max_403_errors)
                max_5xx = st.number_input("Max. 5xx Fehler", value=app_config.max_5xx_errors)
            with col2:
                max_failed = st.number_input("Gesamt fehlgeschlagene Requests", value=app_config.max_failed_requests)
                max_suspicious = st.number_input("Max. verdächtige Pfade", value=app_config.max_suspicious_paths)
                max_rate = st.number_input("Rate-Limit (Requests/Min)", value=app_config.max_requests_per_minute)
                block_dur = st.number_input("Sperrdauer (Sekunden)", value=app_config.block_duration, step=60)
            
            suspicious_paths = st.text_area(
                "Verdächtige Pfade (kommagetrennt)", 
                value=",".join(app_config.suspicious_paths),
                help="Pfade, die sofort als verdächtig markiert werden (z.B. /wp-admin)"
            )

            sensitive_paths = st.text_area(
                "Sensible Pfade (STRENGE BESTRAFUNG, kommagetrennt)", 
                value=",".join(app_config.sensitive_paths),
                help="Fehler auf diesen Pfaden (z.B. /login) erhöhen den Bedrohungsscore dreifach."
            )

            honey_paths = st.text_area(
                "🍯 Honey-Paths (SOFORT-SPERRE, kommagetrennt)", 
                value=",".join(app_config.honey_paths),
                help="Pfade, die bei AUFRUF zur sofortigen permanenten Sperre führen (z.B. /.env)"
            )
            
            enable_blocking = st.checkbox("Automatisches Blocking Aktiv", value=app_config.enable_blocking)
            
            if st.form_submit_button("Sicherheit Speichern"):
                update_setting("max_404_errors", max_404)
                update_setting("max_403_errors", max_403)
                update_setting("max_5xx_errors", max_5xx)
                update_setting("max_failed_requests", max_failed)
                update_setting("max_suspicious_paths", max_suspicious)
                update_setting("max_requests_per_minute", max_rate)
                update_setting("block_duration", block_dur)
                update_setting("suspicious_paths", suspicious_paths)
                update_setting("sensitive_paths", sensitive_paths)
                update_setting("honey_paths", honey_paths)
                update_setting("enable_blocking", enable_blocking)
                st.success("Sicherheitseinstellungen gespeichert!")
                st.rerun()
        
        st.divider()
        st.subheader("🌐 Cloudflare Edge Blocking")
        st.info("Blockiert IPs direkt bei Cloudflare, bevor sie deinen Server erreichen.")
        with st.form("cloudflare_settings"):
            enable_cf = st.checkbox("Cloudflare Integration Aktivieren", value=app_config.enable_cloudflare)
            cf_token = st.text_input("Cloudflare API Token", value=app_config.cloudflare_api_token, type="password", help="Berechtigung: Zone.Firewall Services (Edit)")
            cf_zone = st.text_input("Cloudflare Zone ID", value=app_config.cloudflare_zone_id)
            
            if st.form_submit_button("Cloudflare Speichern"):
                update_setting("enable_cloudflare", enable_cf)
                update_setting("cloudflare_api_token", cf_token)
                update_setting("cloudflare_zone_id", cf_zone)
                st.success("Cloudflare-Einstellungen gespeichert!")
                st.rerun()
        
        st.divider()
        st.subheader("🛡️ CrowdSec Reputation")
        st.info("Prüft IPs gegen die lokale CrowdSec Datenbank (LAPI).")
        with st.form("crowdsec_settings"):
            enable_cs = st.checkbox("CrowdSec Integration Aktivieren", value=app_config.enable_crowdsec)
            cs_url = st.text_input("CrowdSec LAPI URL", value=app_config.crowdsec_api_url)
            cs_key = st.text_input("CrowdSec API Key", value=app_config.crowdsec_api_key, type="password")
            
            if st.form_submit_button("CrowdSec Speichern"):
                update_setting("enable_crowdsec", enable_cs)
                update_setting("crowdsec_api_url", cs_url)
                update_setting("crowdsec_api_key", cs_key)
                st.success("CrowdSec-Einstellungen gespeichert!")
                st.rerun()

    with tab_ai:
        st.subheader("🤖 KI Verhaltensanalyse (OpenRouter)")
        st.info("Nutze LLMs (wie Gemini oder DeepSeek) um das Verhalten von verdächtigen IPs tiefgehend zu analysieren.")
        with st.form("ai_settings"):
            openrouter_key = st.text_input(
                "OpenRouter API Key", 
                value=app_config.openrouter_api_key, 
                type="password",
                help="Erforderlich für KI-Analyse. Hole dir einen Key auf openrouter.ai"
            )
            ai_model = st.text_input(
                "KI Modell", 
                value=app_config.ai_model,
                help="Standard: google/gemini-2.0-flash-lite:free"
            )
            enable_ai_auto = st.checkbox(
                "Auto-KI-Analyse", 
                value=app_config.enable_ai_auto_analysis,
                help="Analysiert jede blockierte IP automatisch im Hintergrund."
            )
            
            if st.form_submit_button("KI-Einstellungen Speichern"):
                update_setting("openrouter_api_key", openrouter_key)
                update_setting("ai_model", ai_model)
                update_setting("enable_ai_auto_analysis", enable_ai_auto)
                st.success("KI-Einstellungen gespeichert!")
                st.rerun()
        
        st.divider()
        st.subheader("🔄 NPM Host Auto-Discovery")
        st.info("Verbindet sich mit der Nginx Proxy Manager Datenbank, um Hosts automatisch zu erkennen.")
        with st.form("npm_db_settings"):
            db_type = st.selectbox("DB Typ", ["mysql", "sqlite"], index=0 if app_config.npm_db_type == "mysql" else 1)
            
            if db_type == "mysql":
                c1, c2 = st.columns(2)
                with c1:
                    n_host = st.text_input("NPM DB Host", value=app_config.npm_db_host)
                    n_user = st.text_input("NPM DB User", value=app_config.npm_db_user)
                with c2:
                    n_port = st.number_input("NPM DB Port", value=app_config.npm_db_port)
                    n_pass = st.text_input("NPM DB Passwort", value=app_config.npm_db_password, type="password")
                n_name = st.text_input("NPM DB Name", value=app_config.npm_db_name)
                n_sqlite = app_config.npm_db_sqlite_path
            else:
                n_sqlite = st.text_input("SQLite Pfad (im Container)", value=app_config.npm_db_sqlite_path)
                n_host, n_user, n_port, n_pass, n_name = "", "", 3306, "", ""

            if st.form_submit_button("NPM-Verbindung Speichern"):
                update_setting("npm_db_type", db_type)
                update_setting("npm_db_host", n_host)
                update_setting("npm_db_port", n_port)
                update_setting("npm_db_user", n_user)
                update_setting("npm_db_password", n_pass)
                update_setting("npm_db_name", n_name)
                update_setting("npm_db_sqlite_path", n_sqlite)
                st.success("NPM-Verbindungseinstellungen gespeichert!")
                st.rerun()

    with tab_notify:
        st.subheader("Alerting Konfiguration")
        with st.form("notification_settings"):
            st.write("**Webhook (Discord / Slack)**")
            webhook = st.text_input(
                "Webhook URL", 
                value=app_config.webhook_url,
                placeholder="https://discord.com/api/webhooks/...",
                help="Discord, Slack oder kompatible Webhooks"
            )
            
            st.divider()
            st.write("**Telegram Bot**")
            tg_token = st.text_input("Telegram Bot Token", value=app_config.telegram_bot_token, type="password")
            tg_chat = st.text_input("Telegram Chat ID", value=app_config.telegram_chat_id)
            
            st.divider()
            notify = st.checkbox("Benachrichtigung bei Blockierung senden", value=app_config.notify_on_block)
            
            if st.form_submit_button("Alerting Speichern"):
                update_setting("webhook_url", webhook)
                update_setting("telegram_bot_token", tg_token)
                update_setting("telegram_chat_id", tg_chat)
                update_setting("notify_on_block", notify)
                st.success("Alerting-Einstellungen gespeichert!")
                st.rerun()

    with tab_user:
        st.subheader("👥 Benutzerverwaltung")
        from src.database import list_users, create_user, update_user_totp_secret, get_user
        from src.auth import hash_password
        import pyotp
        import qrcode
        
        users = list_users()
        st.write(f"Aktuelle Benutzer: {len(users)}")
        st.table(users)
        
        with st.expander("➕ Neuen Benutzer hinzufügen"):
            with st.form("new_user_form", clear_on_submit=True):
                new_name = st.text_input("Benutzername")
                new_pass = st.text_input("Passwort", type="password")
                new_role = st.selectbox("Rolle", ["admin", "viewer"])
                if st.form_submit_button("Erstellen"):
                    if new_name and new_pass:
                        hashed = hash_password(new_pass)
                        if create_user(new_name, hashed, new_role):
                            st.success(f"Benutzer {new_name} erstellt.")
                            st.rerun()
                        else:
                            st.error("Fehler beim Erstellen (Benutzername evtl. schon vergeben).")

        with st.expander("🔐 Zwei-Faktor-Authentifizierung (MFA) einrichten"):
            current_user = st.session_state.get("user", {})
            if not current_user:
                st.warning("Bitte logge dich erneut ein, um MFA zu konfigurieren.")
            else:
                db_user = get_user(current_user["username"])
                
                if db_user and db_user.get("totp_secret"):
                    st.success("✅ MFA ist für deinen Account aktiviert.")
                    if st.button("MFA Deaktivieren", type="primary"):
                        if update_user_totp_secret(current_user["username"], None):
                            st.success("MFA wurde deaktiviert.")
                            st.rerun()
                else:
                    st.info("MFA ist aktuell deaktiviert. Generiere einen neuen Code, um es einzurichten.")
                    if "totp_secret" not in st.session_state:
                        st.session_state.totp_secret = pyotp.random_base32()
                    
                    secret = st.session_state.totp_secret
                    totp = pyotp.TOTP(secret)
                    uri = totp.provisioning_uri(name=current_user.get("username", "user"), issuer_name="NPM Monitor")
                    
                    st.write("**Schritt 1:** Scanne diesen QR-Code mit einer Authenticator-App (z.B. Google Authenticator, Authy, Aegis).")
                    
                    qr = qrcode.make(uri)
                    st.image(qr.get_image(), width=200)
                    
                    st.write(f"Oder gib diesen Code manuell ein: `{secret}`")
                    
                    st.write("**Schritt 2:** Gib den aktuellen 6-stelligen Code ein, um die Einrichtung abzuschließen.")
                    with st.form("verify_mfa"):
                        code = st.text_input("6-stelliger Code")
                        if st.form_submit_button("MFA Aktivieren"):
                            if totp.verify(code):
                                if update_user_totp_secret(current_user["username"], secret):
                                    st.success("MFA erfolgreich aktiviert!")
                                    st.rerun()
                            else:
                                st.error("Falscher Code. Bitte versuche es erneut.")

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
