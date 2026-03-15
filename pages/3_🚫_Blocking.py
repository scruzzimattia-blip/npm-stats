import streamlit as st

from src.components.blocking import render_asn_blocking, render_blocked_ips, render_blocking_config
from src.ui_utils import handle_sync_button, init_page, render_common_sidebar


def main():
    init_page("Security", "🚫")
    st.title("🚫 Blocking & Sicherheit")

    handle_sync_button()

    # We still render the sidebar for consistency, though we might not need all filters here
    render_common_sidebar()

    tab1, tab2 = st.tabs(["Geblockte IPs", "Konfiguration"])

    with tab1:
        render_blocked_ips()
        render_asn_blocking()

    with tab2:
        render_blocking_config()

if __name__ == "__main__":
    main()
