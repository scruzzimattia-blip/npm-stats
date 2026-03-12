"""Streamlit UI components for NPM Monitor."""

from .blocking import render_blocked_ips, render_blocking_config
from .charts import (
    render_bandwidth_analysis,
    render_charts,
    render_error_paths,
    render_geo_analysis,
    render_referer_analysis,
    render_user_agent_analysis,
)
from .sidebar import render_sidebar
from .tables import render_geo_summary, render_metrics, render_request_log, render_top_ips

__all__ = [
    "render_charts",
    "render_error_paths",
    "render_geo_analysis",
    "render_referer_analysis",
    "render_user_agent_analysis",
    "render_bandwidth_analysis",
    "render_sidebar",
    "render_metrics",
    "render_top_ips",
    "render_request_log",
    "render_blocked_ips",
    "render_blocking_config",
    "render_geo_summary",
]
