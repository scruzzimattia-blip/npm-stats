"""Notification module for sending alerts via webhooks."""

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from .config import app_config

logger = logging.getLogger(__name__)


def send_notification(ip: str, reason: str, block_until: datetime) -> bool:
    """Send a notification via webhook (Discord, Slack, Telegram or generic)."""
    if not app_config.notify_on_block:
        return False

    success = False
    
    # Common message parts
    title = "🚫 IP Blocked"
    description = (
        f"**IP Address:** `{ip}`\n"
        f"**Reason:** {reason}\n"
        f"**Blocked Until:** {block_until.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Webhook Notifications (Discord/Slack/Generic)
    if app_config.webhook_url:
        try:
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
                if 200 <= response.status < 300:
                    logger.info(f"Webhook notification sent for IP {ip}")
                    success = True
                else:
                    logger.error(f"Failed to send webhook notification: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")

    # Telegram Notifications
    if app_config.telegram_bot_token and app_config.telegram_chat_id:
        try:
            telegram_msg = f"<b>{title}</b>\n\nIP: <code>{ip}</code>\nGrund: {reason}\nSperre bis: {block_until.strftime('%Y-%m-%d %H:%M:%S')}"
            telegram_url = f"https://api.telegram.org/bot{app_config.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": app_config.telegram_chat_id,
                "text": telegram_msg,
                "parse_mode": "HTML"
            }
            
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                telegram_url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "NPM-Monitor"},
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if 200 <= response.status < 300:
                    logger.info(f"Telegram notification sent for IP {ip}")
                    success = True
                else:
                    logger.error(f"Failed to send Telegram notification: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")

    return success
