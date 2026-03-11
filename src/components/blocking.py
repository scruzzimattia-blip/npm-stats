"""Blocked IPs dashboard component."""

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from ..blocking import get_blocker
from ..config import app_config
from ..database import get_blocked_ips, remove_blocked_ip

logger = logging.getLogger(__name__)


@st.cache_data(ttl=10)
def _get_cached_blocked_ips():
    """Get blocked IPs with caching."""
    try:
        return get_blocked_ips(active_only=True)
    except Exception as e:
        logger.error(f"Error getting blocked IPs: {e}")
        return []


def render_blocked_ips():
    """Render the blocked IPs management interface."""
    st.subheader("🚫 Blocked IPs")

    if not app_config.enable_blocking:
        st.info("IP blocking is disabled. Enable it in configuration to use this feature.")
        return

    blocker = get_blocker()

    # Statistics (fast, in-memory)
    stats = blocker.get_stats()
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Currently Blocked", stats["total_blocked"])
    with col2:
        st.metric("Whitelisted IPs", stats["whitelisted"])
    with col3:
        st.metric("Tracked IPs", stats["tracked_ips"])

    st.markdown("---")

    # Get blocked IPs from database (with caching)
    try:
        blocked_ips = _get_cached_blocked_ips()

        if not blocked_ips:
            st.info("No IPs are currently blocked.")
            return

        # Limit display to last 100 IPs for performance
        display_ips = blocked_ips[:100]
        if len(blocked_ips) > 100:
            st.warning(f"Showing last 100 of {len(blocked_ips)} blocked IPs")

        # Create DataFrame
        df_data = []
        for ip, reason, blocked_at, block_until, is_manual in display_ips:
            df_data.append(
                {
                    "IP Address": ip,
                    "Reason": reason[:50] + "..." if len(reason) > 50 else reason,
                    "Blocked": blocked_at.strftime("%m/%d %H:%M"),
                    "Until": block_until.strftime("%m/%d %H:%M"),
                    "Type": "Manual" if is_manual else "Auto",
                }
            )

        df = pd.DataFrame(df_data)

        # Display table (simplified)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Unblock IPs
        st.markdown("### Unblock IPs")

        selected_ips = st.multiselect(
            "Select IPs to unblock",
            options=[ip[0] for ip in display_ips],
            key="unblock_ips",
            max_selections=10,
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            unblock_button = st.button("Unblock Selected IPs", type="secondary")
        with col2:
            refresh_button = st.button("🔄 Refresh", type="primary")

        if refresh_button:
            _get_cached_blocked_ips.clear()
            st.rerun()

        if unblock_button:
            if not selected_ips:
                st.warning("Please select IPs to unblock")
            else:
                with st.spinner("Unblocking IPs..."):
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
                            st.error(f"Failed to unblock {ip}")

                    if unblocked_count > 0:
                        # Clear cache
                        _get_cached_blocked_ips.clear()
                        st.success(f"Unblocked {unblocked_count} IP(s)")
                        # Use session state to force refresh instead of rerun
                        st.session_state.unblock_success = True

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
        st.write(f"- Block Duration: {app_config.block_duration}s ({app_config.block_duration // 60}min)")
        st.write(f"- Blocking Enabled: {app_config.enable_blocking}")
        st.write(f"- Suspicious Paths: {len(app_config.suspicious_paths)} patterns")

    if app_config.suspicious_paths:
        with st.expander("View Suspicious Paths", expanded=False):
            for path in app_config.suspicious_paths[:10]:
                st.code(path, language="text")
            if len(app_config.suspicious_paths) > 10:
                st.info(f"... and {len(app_config.suspicious_paths) - 10} more")