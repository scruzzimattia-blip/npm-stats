import streamlit as st
import pandas as pd
import plotly.express as px
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
    render_user_agent_analysis,
    render_geo_summary,
    render_npm_hosts_status
)
from src.components.maps import render_geo_map
from src.utils.whois import get_whois_info
from src.crowdsec import get_crowdsec_manager
from src.database import get_ai_reports
from src.ai_analyzer import AIAnalyzer
from src.config import app_config

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
        limit=5000 # More data for geo analysis
    )
    
    # Load optimized aggregated geo data
    from src.ui_utils import _cached_geo_summary
    geo_stats = _cached_geo_summary(
        hosts=selected_hosts,
        start_date=start_date,
        end_date=end_date
    )

    # Main Row: Map and Geo Table
    col_map, col_stats = st.columns([2, 1])
    
    with col_map:
        render_geo_map(df)
    
    with col_stats:
        render_geo_summary(df, geo_stats)
    
    st.divider()
    
    # Analysis Row
    col1, col2 = st.columns(2)
    with col1:
        render_geo_analysis(df, geo_stats)
    with col2:
        render_user_agent_analysis(df)
        
    st.divider()
    
    st.subheader("🕵️ Einzel-IP Untersuchung")
    ip_to_check = st.text_input("IP-Adresse eingeben (z.B. für Whois-Abfrage)")
    if ip_to_check:
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("Whois abfragen", type="primary", use_container_width=True):
                with st.spinner(f"Whois-Daten für {ip_to_check} werden abgerufen..."):
                    whois_data = get_whois_info(ip_to_check)
                    if whois_data:
                        st.success("Whois-Daten erfolgreich abgerufen!")
                        col_w1, col_w2 = st.columns(2)
                        with col_w1:
                            asn = whois_data.get("asn", "N/A")
                            st.metric("ASN", asn)
                            st.metric("Country", whois_data.get("asn_country_code", "N/A"))
                        with col_w2:
                            net_name = whois_data.get("network_name", "N/A")
                            st.metric("Netzwerk", net_name)
                            st.write("**Abuse Emails:**")
                            for email in whois_data.get("abuse_emails", []):
                                st.code(email)
                            if not whois_data.get("abuse_emails"):
                                st.write("Keine Abuse-Emails gefunden.")
                        
                        # ASN Blocking Button
                        if asn != "N/A":
                            st.divider()
                            st.warning(f"Sperre das gesamte Netzwerk ({net_name}, ASN {asn})?")
                            if st.button(f"🚫 ASN {asn} komplett sperren", use_container_width=True):
                                from src.database import add_asn_block
                                if add_asn_block(asn, net_name, f"Manuelle Sperre via IP-Analyse ({ip_to_check})"):
                                    st.success(f"Netzwerk ASN {asn} wurde zur Sperrliste hinzugefügt.")
                                    # Clear blocker cache
                                    from src.blocking import get_blocker
                                    get_blocker().blocked_asns.clear()
                                else:
                                    st.error("Fehler beim Sperren des Netzwerks.")
                    else:
                        st.error("Whois-Abfrage fehlgeschlagen oder 'ipwhois' ist nicht installiert.")
        
        with col_btn2:
            if st.button("CrowdSec Reputation prüfen", use_container_width=True):
                cs_manager = get_crowdsec_manager()
                if cs_manager:
                    with st.spinner(f"Prüfe {ip_to_check} bei CrowdSec..."):
                        decision = cs_manager.get_ip_reputation(ip_to_check)
                        if decision:
                            st.error(f"⚠️ IP ist bei CrowdSec gelistet!")
                            st.json(decision)
                        else:
                            st.success("✅ Keine negativen Einträge bei CrowdSec gefunden.")
                else:
                    st.warning("CrowdSec Integration ist nicht konfiguriert oder deaktiviert.")
        
        # AI Analysis Section
        st.divider()
        st.subheader("🤖 KI-Verhaltensanalyse (OpenRouter)")
        
        ai_reports = get_ai_reports(ip_to_check)
        if ai_reports:
            for report in ai_reports:
                with st.expander(f"KI-Bericht vom {report['analyzed_at'].strftime('%Y-%m-%d %H:%M')} ({report['model']})", expanded=True):
                    st.markdown(report['report'])
                    st.caption(f"Bedrohungslevel: {report['threat_level']}")
        else:
            st.info("Noch keine KI-Analyse für diese IP vorhanden.")
            
        if st.button("🚀 Neue KI-Analyse starten", use_container_width=True):
            if not app_config.openrouter_api_key:
                st.error("OpenRouter API Key fehlt in den Einstellungen!")
            else:
                with st.spinner("KI analysiert das Verhalten..."):
                    analyzer = AIAnalyzer()
                    result = analyzer.analyze_ip(ip_to_check)
                    if result:
                        st.success("Analyse abgeschlossen!")
                        st.rerun()
                    else:
                        st.error("Analyse fehlgeschlagen. Prüfe die Logs des npm-ai Containers.")

    st.divider()
    st.subheader("🌐 Provider & Netzwerk Verteilung")
    
    # Simple ASN aggregation for visualization (using whois info from the top ips summary if we had it, 
    # but here we can at least show country distribution as a proxy or if we have ASN in DF)
    # Since WHOIS is expensive, we use the country_code for the chart if ASN is not in DF
    if not df.empty:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.write("**Top Länder (Traffic)**")
            country_counts = df["country_code"].value_counts().reset_index()
            country_counts.columns = ["Land", "Anfragen"]
            fig_country = px.pie(country_counts.head(10), values="Anfragen", names="Land", hole=0.4,
                                color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_country, use_container_width=True)
            
        with col_c2:
            st.write("**Fehlerrate nach Land**")
            error_geo = df.groupby("country_code").agg(
                total=("status", "count"),
                errors=("status", lambda x: (x >= 400).sum())
            ).reset_index()
            error_geo["Fehlerrate"] = (error_geo["errors"] / error_geo["total"] * 100).round(1)
            error_geo = error_geo.sort_values("errors", ascending=False).head(10)
            fig_err = px.bar(error_geo, x="country_code", y="Fehlerrate", color="errors",
                            labels={"country_code": "Land", "Fehlerrate": "Fehlerrate (%)"},
                            color_continuous_scale="Reds")
            st.plotly_chart(fig_err, use_container_width=True)

    st.divider()
    render_referer_analysis(df)
    
    st.divider()
    render_npm_hosts_status()

if __name__ == "__main__":
    main()
