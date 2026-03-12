import streamlit as st
from src.ui_utils import init_page

def main():
    init_page("Willkommen", "🏠")
    
    st.title("🌐 NPM Traffic Monitor")
    
    st.markdown("""
    ### Willkommen beim NPM Traffic Monitor!
    
    Dieses Dashboard hilft dir, den Traffic deines Nginx Proxy Managers in Echtzeit zu überwachen, 
    Angriffsmuster zu erkennen und bösartige IPs automatisch zu sperren.
    
    #### 🚀 Schnellstart
    Wähle eine Seite aus dem Menü links aus:
    
    *   **📊 Übersicht**: Wichtige Metriken, Traffic-Charts und Fehleranalyse.
    *   **🔎 IP-Analyse**: Detaillierte Statistiken nach IP-Adresse und geografischer Herkunft.
    *   **🚫 Blocking**: Verwaltung der Sperrliste und Sicherheitseinstellungen.
    *   **⚙️ Einstellungen**: Systemkonfiguration und Datenbank-Status.
    
    ---
    *Tipp: Nutze den 🔄 Sync Button oben rechts auf jeder Seite, um die neuesten Logs manuell einzulesen.*
    """)
    
    # Show some quick stats
    from src.database import get_database_info
    db_info = get_database_info()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Verarbeitete Requests", db_info["total_rows"])
    col2.metric("Aktive IP-Sperren", db_info["blocked_count"])
    col3.metric("Datenbankgröße", db_info["table_size"])

if __name__ == "__main__":
    main()
