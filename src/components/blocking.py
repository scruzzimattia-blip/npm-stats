"""Blocked IPs dashboard component."""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from ..blocking import get_blocker
from ..config import app_config
from ..database import (
    add_asn_block,
    add_blocked_ip,
    add_to_whitelist,
    get_asn_blocklist,
    get_blocked_ips_history,
    get_blocklist_with_ai_status,
    get_whitelist,
    remove_asn_block,
    remove_blocked_ip,
    remove_from_whitelist,
)

logger = logging.getLogger(__name__)


@st.cache_data(ttl=10)
def _get_cached_blocklist_rich():
    """Get rich blocklist with caching."""
    try:
        return get_blocklist_with_ai_status()
    except Exception as e:
        logger.error(f"Error getting rich blocklist: {e}")
        return []


def render_blocked_ips():
    """Render the enhanced blocked IPs management interface."""
    st.subheader("🚫 Aktive Sperrliste")

    blocker = get_blocker()

    # 1. Action Buttons & Quick Controls
    col_actions1, col_actions2 = st.columns([2, 1])

    with col_actions1:
        with st.expander("➕ IP manuell sperren"):
            with st.form("manual_block_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    manual_ip = st.text_input("IP Adresse", placeholder="z.B. 1.2.3.4")
                with c2:
                    manual_reason = st.text_input("Grund", value="Manuelle Sperre")

                c3, c4 = st.columns(2)
                with c3:
                    manual_duration = st.number_input("Dauer", min_value=1, value=60, help="In Minuten")
                with c4:
                    duration_unit = st.selectbox("Einheit", ["Minuten", "Stunden", "Tage"])

                if st.form_submit_button("Sperre anlegen", type="primary", use_container_width=True):
                    if manual_ip:
                        mult = {"Minuten": 1, "Stunden": 60, "Tage": 1440}
                        until = datetime.now(timezone.utc) + timedelta(minutes=manual_duration * mult[duration_unit])
                        add_blocked_ip(manual_ip, manual_reason, until, is_manual=True)
                        blocker.block_ip(manual_ip, manual_reason, until)
                        st.success(f"IP {manual_ip} wurde gesperrt.")
                        _get_cached_blocklist_rich.clear()
                        st.rerun()

    with col_actions2:
        if st.button(
            "🗑️ Alle Sperren aufheben",
            type="secondary",
            use_container_width=True,
            help="Entfernt ALLE aktiven Sperren aus der Datenbank und Firewall",
        ):
            from ..database import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE blocklist SET unblocked_at = NOW() WHERE unblocked_at IS NULL")
            _get_cached_blocklist_rich.clear()
            st.toast("Alle IPs wurden entsperrt.", icon="✅")
            st.rerun()

    # 2. Rich Statistics
    rich_blocklist = _get_cached_blocklist_rich()
    stats = blocker.get_stats()

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("Aktive Sperren", len(rich_blocklist))
    col_s2.metric("Whitelist", stats["whitelisted"])

    # Calculate most common reason
    if rich_blocklist:
        reasons = [r["reason"] for r in rich_blocklist]
        top_reason = max(set(reasons), key=reasons.count)
        col_s3.metric("Top Grund", top_reason.split("(")[0].strip()[:15])
    else:
        col_s3.metric("Top Grund", "-")

    col_s4.metric("Überwachte IPs", stats["tracked_ips"])

    st.divider()

    # 3. Search and Filter
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_term = st.text_input("🔍 Sperrliste durchsuchen (IP oder Grund)", placeholder="Suchen...")
    with search_col2:
        filter_type = st.selectbox("Typ", ["Alle", "Auto", "Manuell"])

    # Apply filters
    filtered_list = rich_blocklist
    if search_term:
        filtered_list = [
            r
            for r in filtered_list
            if search_term.lower() in r["ip_address"].lower() or search_term.lower() in r["reason"].lower()
        ]
    if filter_type != "Alle":
        is_manual_filter = filter_type == "Manuell"
        filtered_list = [r for r in filtered_list if r["is_manual"] == is_manual_filter]

    if not filtered_list:
        st.info("Keine Sperren gefunden, die den Kriterien entsprechen.")
    else:
        # Create Display DataFrame
        display_data = []
        for r in filtered_list:
            display_data.append(
                {
                    "IP Adresse": r["ip_address"],
                    "Grund": r["reason"],
                    "Gesperrt seit": r["blocked_at"].strftime("%Y-%m-%d %H:%M"),
                    "Bis": "PERMANENT" if r.get("is_permanent") else r["block_until"].strftime("%Y-%m-%d %H:%M"),
                    "Typ": "👤 Manuell" if r["is_manual"] else "🤖 Auto",
                    "Permanent": "🔒 Ja" if r.get("is_permanent") else "➖",
                    "KI": "🧠 Ja" if r["ai_report_count"] > 0 else "➖",
                }
            )

        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 4. Multi-Select Actions
        st.write(f"**Aktionen für {len(filtered_list)} Einträge:**")
        col_m1, col_s_btn = st.columns([3, 1])

        with col_m1:
            selected_to_unblock = st.multiselect(
                "IPs zum Entsperren auswählen", options=[r["ip_address"] for r in filtered_list], max_selections=50
            )

        with col_s_btn:
            if st.button("🔓 Entsperren", type="primary", use_container_width=True):
                if selected_to_unblock:
                    for ip in selected_to_unblock:
                        remove_blocked_ip(ip)
                        blocker.unblock_ip(ip)
                    st.success(f"{len(selected_to_unblock)} IPs entsperrt.")
                    _get_cached_blocklist_rich.clear()
                    st.rerun()

        # 5. Export
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Sperrliste als CSV exportieren",
            data=csv,
            file_name=f"blocklist_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    # 6. Whitelist Section (Enhanced)
    st.divider()
    st.subheader("⚪ Whitelist (Ausnahmen)")

    w_col1, w_col2 = st.columns([1, 2])
    with w_col1:
        with st.form("add_whitelist_form", clear_on_submit=True):
            st.write("**Neu hinzufügen**")
            w_ip = st.text_input("IP Adresse")
            w_reason = st.text_input("Notiz", value="Vertrauenswürdig")
            if st.form_submit_button("Zur Whitelist", use_container_width=True):
                if w_ip:
                    add_to_whitelist(w_ip, w_reason)
                    st.success("Hinzugefügt.")
                    st.rerun()

    with w_col2:
        try:
            whitelist = get_whitelist()
            if whitelist:
                w_df = pd.DataFrame(whitelist)
                # handle different column names if necessary
                if "ip_address" in w_df.columns:
                    w_df.columns = ["IP Adresse", "Notiz", "Hinzugefügt"]

                st.dataframe(w_df, use_container_width=True, hide_index=True)

                ips_to_remove = st.multiselect("Von Whitelist entfernen", options=w_df["IP Adresse"].tolist())
                if st.button("Entfernen", disabled=not ips_to_remove):
                    for ip in ips_to_remove:
                        remove_from_whitelist(ip)
                    st.rerun()
            else:
                st.info("Keine Ausnahmen definiert.")
        except Exception as e:
            st.error(f"Fehler: {e}")

    # 7. History Section
    st.divider()
    st.subheader("📜 Sperr-Historie")

    try:
        history = get_blocked_ips_history(limit=100)
        if history:
            hist_data = []
            for r in history:
                hours = r.get("blocked_hours", 0)
                hist_data.append(
                    {
                        "IP": r["ip_address"],
                        "Grund": r["reason"],
                        "Gesperrt": r["blocked_at"].strftime("%Y-%m-%d %H:%M") if r["blocked_at"] else "-",
                        "Entsperrt": r["unblocked_at"].strftime("%Y-%m-%d %H:%M") if r["unblocked_at"] else "-",
                        "Dauer (h)": f"{hours:.1f}" if hours else "-",
                        "Typ": "👤 Manuell" if r["is_manual"] else "🤖 Auto",
                    }
                )

            hist_df = pd.DataFrame(hist_data)
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

            csv_hist = hist_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Historie als CSV exportieren",
                data=csv_hist,
                file_name=f"blocklist_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info("Keine aufgehobenen Sperren vorhanden.")
    except Exception as e:
        st.error(f"Fehler beim Laden der Historie: {e}")


def render_asn_blocking():
    """Render the ASN-level network blocking interface."""
    st.divider()
    st.subheader("🏢 Netzwerk-Sperren (ASN)")
    st.info("Sperrt ganze Rechenzentren oder Provider-Netzwerke.")

    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form("add_asn_form", clear_on_submit=True):
            st.write("**ASN sperren**")
            asn_val = st.text_input("ASN Nummer", placeholder="z.B. 24940")
            asn_desc = st.text_input("Beschreibung", placeholder="z.B. Hetzner Online GmbH")
            asn_reason = st.text_input("Grund", value="Data-Center Blocking")

            if st.form_submit_button("Netzwerk sperren", use_container_width=True):
                if asn_val:
                    add_asn_block(asn_val, asn_desc, asn_reason)
                    st.success(f"ASN {asn_val} gesperrt.")
                    # Clear blocker cache
                    get_blocker().blocked_asns.clear()
                    st.rerun()

    with col2:
        try:
            asn_list = get_asn_blocklist()
            if asn_list:
                asn_df = pd.DataFrame(asn_list)
                asn_df.columns = ["ASN", "Netzwerk", "Gesperrt am", "Grund"]
                st.dataframe(asn_df, use_container_width=True, hide_index=True)

                asns_to_remove = st.multiselect("Sperre aufheben für ASN", options=asn_df["ASN"].tolist())
                if st.button("ASN freigeben", disabled=not asns_to_remove):
                    for asn in asns_to_remove:
                        remove_asn_block(asn)
                    get_blocker().blocked_asns.clear()
                    st.rerun()
            else:
                st.info("Keine Netzwerk-Sperren aktiv.")
        except Exception as e:
            st.error(f"Fehler beim Laden der ASN-Sperrliste: {e}")


def render_blocking_config():
    """Render blocking configuration display with live update links."""
    st.subheader("⚙️ Schwellenwerte & Regeln")
    st.info("Diese Einstellungen können in der Seite 'Settings' geändert werden.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Max 404", app_config.max_404_errors)
    c2.metric("Max 403", app_config.max_403_errors)
    c3.metric("Max Failed", app_config.max_failed_requests)

    st.write("**Aktive Sicherheits-Features:**")
    sc1, sc2, sc3 = st.columns(3)
    sc1.checkbox("Auto-Blocking", value=app_config.enable_blocking, disabled=True)
    sc2.checkbox("Cloudflare Edge", value=app_config.enable_cloudflare, disabled=True)
    sc3.checkbox("CrowdSec LAPI", value=app_config.enable_crowdsec, disabled=True)

    if app_config.suspicious_paths:
        with st.expander(f"Verdächtige Pfad-Muster ({len(app_config.suspicious_paths)})", expanded=False):
            st.write(", ".join([f"`{p}`" for p in app_config.suspicious_paths]))
