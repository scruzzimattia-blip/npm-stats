"""Blocked IPs dashboard component."""

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from ..blocking import get_blocker
from ..config import app_config
from ..database import get_blocked_ips, remove_blocked_ip

logger = logging.getLogger(__name__)


def render_blocked_ips():
    """Render the blocked IPs management interface."""
    st.subheader("🚫 Blocked IPs")

    if not app_config.enable_blocking:
        st.info("IP blocking is disabled. Enable it in configuration to use this feature.")
        return

    blocker = get_blocker()

    # Statistics
    stats = blocker.get_stats()
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Currently Blocked", stats["total_blocked"])
    with col2:
        st.metric("Whitelisted IPs", stats["whitelisted"])
    with col3:
        st.metric("Tracked IPs", stats["tracked_ips"])

    st.markdown("---")

    # Get blocked IPs from database
    try:
        blocked_ips = get_blocked_ips(active_only=True)

        if not blocked_ips:
            st.info("No IPs are currently blocked.")
            return

        # Create DataFrame
        df_data = []
        for ip, reason, blocked_at, block_until, is_manual in blocked_ips:
            df_data.append(
                {
                    "IP Address": ip,
                    "Reason": reason,
                    "Blocked At": blocked_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "Block Until": block_until.strftime("%Y-%m-%d %H:%M:%S"),
                    "Manual": "Yes" if is_manual else "No",
                }
            )

        df = pd.DataFrame(df_data)

        # Display table
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "IP Address": st.column_config.TextColumn("IP Address", width="medium"),
                "Reason": st.column_config.TextColumn("Reason", width="large"),
                "Blocked At": st.column_config.TextColumn("Blocked At", width="medium"),
                "Block Until": st.column_config.TextColumn("Block Until", width="medium"),
                "Manual": st.column_config.TextColumn("Manual", width="small"),
            },
        )

        # Unblock IPs
        st.markdown("### Unblock IPs")

        selected_ips = st.multiselect(
            "Select IPs to unblock", options=[ip[0] for ip in blocked_ips], key="unblock_ips"
        )

        if st.button("Unblock Selected IPs", type="secondary"):
            unblocked_count = 0
            for ip in selected_ips:
                try:
                    # Remove from database
                    if remove_blocked_ip(ip):
                        # Remove from memory
                        blocker.unblock_ip(ip)
                        unblocked_count += 1
                        logger.info(f"Manually unblocked IP: {ip}")
                except Exception as e:
                    logger.error(f"Error unblocking IP {ip}: {e}")

            if unblocked_count > 0:
                st.success(f"Successfully unblocked {unblocked_count} IP(s)")
                st.rerun()

    except Exception as e:
        logger.error(f"Error loading blocked IPs: {e}")
        st.error(f"Error loading blocked IPs: {e}")


def render_blocking_config():
    """Render blocking configuration display."""
    st.subheader("⚙️ Blocking Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Thresholds:**")
        st.write(f"- Max 404 Errors: {app_config.max_404_errors}")
        st.write(f"- Max 403 Errors: {app_config.max_403_errors}")
        st.write(f"- Max 5xx Errors: {app_config.max_5xx_errors}")
        st.write(f"- Max Failed Requests: {app_config.max_failed_requests}")

    with col2:
        st.write("**Settings:**")
        st.write(f"- Block Duration: {app_config.block_duration} seconds")
        st.write(f"- Blocking Enabled: {app_config.enable_blocking}")
        st.write(f"- Suspicious Paths: {len(app_config.suspicious_paths)} patterns")

    if app_config.suspicious_paths:
        with st.expander("View Suspicious Paths"):
            for path in app_config.suspicious_paths:
                st.code(path, language="text")


def render_blocking_stats():
    """Render blocking statistics."""
    st.subheader("📊 Blocking Statistics")

    blocker = get_blocker()
    stats = blocker.get_stats()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Blocked", stats["total_blocked"], delta=None)

    with col2:
        st.metric("Whitelisted", stats["whitelisted"], delta=None)

    # Recent blocks
    try:
        blocked_ips = get_blocked_ips(active_only=False)

        if blocked_ips:
            st.markdown("### Recent Blocking Activity")

            # Group by reason
            reasons = {}
            for ip, reason, blocked_at, block_until, is_manual in blocked_ips[:10]:
                if reason not in reasons:
                    reasons[reason] = 0
                reasons[reason] += 1

            if reasons:
                st.bar_chart(reasons)

    except Exception as e:
        logger.error(f"Error loading blocking stats: {e}")