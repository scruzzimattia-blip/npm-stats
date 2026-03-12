"""Notification module for sending alerts via webhooks."""

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from .config import app_config

logger = logging.getLogger(__name__)


def send_notification(ip: str, reason: str, block_until: datetime) -> bool:
    """Send a notification via webhook (Discord, Slack, or generic)."""
    if not app_config.webhook_url or not app_config.notify_on_block:
        return False

    try:
        title = "🚫 IP Blocked"
        description = (
            f"**IP Address:** `{ip}`\n"
            f"**Reason:** {reason}\n"
            f"**Blocked Until:** {block_until.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Discord format (rich embed)
        if "discord.com" in app_config.webhook_url:
            payload = {
                "embeds": [
                    {
                        "title": title,
                        "description": description,
                        "color": 15158332,  # Red
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "footer": {"text": "NPM Monitor Alert"},
                    }
                ]
            }
        # Generic/Slack format
        else:
            payload = {
                "text": f"*{title}*\n{description}",
            }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            app_config.webhook_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "NPM-Monitor"},
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status >= 200 and response.status < 300:
                logger.info(f"Notification sent for IP {ip}")
                return True
            else:
                logger.error(f"Failed to send notification: HTTP {response.status}")
                return False

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False
