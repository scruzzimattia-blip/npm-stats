
from datetime import datetime, timezone

import streamlit as st

from src.ui_utils import init_page, render_common_sidebar
from src.utils.health import check_npm_status, get_system_health


def main():
    init_page("Systemstatus", "🏥")
    st.title("🏥 System-Gesundheit")

    render_common_sidebar()

    health = get_system_health()

    # 1. Overview Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Datenbank", "✅ OK" if health["database"] else "❌ Fehler")
    with col2:
        st.metric("Redis Cache", "✅ OK" if health["redis"] else "❌ Fehler")
    with col3:
        st.metric("Log-Worker", "🟢 Läuft" if health["log_worker"] else "🔴 Gestoppt")
    with col4:
        st.metric("Firewall", f"🛡️ {health['firewall']['rules_count']} Regeln" if health["firewall"]["has_permissions"] else "⚠️ Kein Zugriff")

    st.divider()

    # 2. Detailed Status
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📡 NPM Verfügbarkeit")
        npm_status = check_npm_status()
        for port, open in npm_status.items():
            status_text = "Offen" if open else "Geschlossen"
            status_icon = "✅" if open else "❌"
            st.write(f"{status_icon} Port {port}: **{status_text}**")

        st.subheader("🔥 Firewall Details")
        fw = health["firewall"]
        st.write(f"Verfügbar: {'✅' if fw['available'] else '❌'}")
        st.write(f"Berechtigungen: {'✅' if fw['has_permissions'] else '❌'}")
        st.write(f"Parent-Chain: `{fw['parent_chain']}`")
        st.write(f"Aktive Sperr-Regeln: `{fw['rules_count']}`")

    with col_right:
        st.subheader("📊 Daten-Aktualität")
        if health["last_data"]:
            last_dt = health["last_data"]
            # Ensure last_dt is timezone aware for comparison
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            diff = (now - last_dt).total_seconds()

            if diff < 300:
                st.success(f"Daten sind aktuell (vor {int(diff/60)} Min.)")
            elif diff < 3600:
                st.warning(f"Daten sind verzögert (vor {int(diff/60)} Min.)")
            else:
                st.error(f"Daten sind veraltet (vor {int(diff/3600)} Std.)")

            st.write(f"Letzter Eintrag: `{last_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}`")
        else:
            st.error("Keine Traffic-Daten in der Datenbank gefunden.")

        st.subheader("⚙️ System-Info")
        st.write(f"Zeitstempel (UTC): `{datetime.now(timezone.utc).strftime('%H:%M:%S')}`")
        if st.button("🔄 Status aktualisieren", use_container_width=True):
            st.rerun()

    # 3. Troubleshooting
    with st.expander("🛠️ Fehlerbehebung"):
        st.write("""
        **Log-Worker läuft nicht?**
        Prüfe den Status via SSH:
        `systemctl status npm-log-worker`

        **Keine Firewall-Berechtigungen?**
        Stelle sicher, dass der Benutzer, unter dem das Dashboard läuft, in der `/etc/sudoers` Datei für `iptables` freigeschaltet ist oder die `NET_ADMIN` Capability besitzt.

        **Datenbankverbindung fehlgeschlagen?**
        Prüfe die `.env` Datei und stelle sicher, dass der PostgreSQL Container läuft.
        """)

if __name__ == "__main__":
    main()
