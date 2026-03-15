"""Notification module for sending alerts via webhooks."""

import json
import logging
import smtplib
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import app_config

logger = logging.getLogger(__name__)


def send_email_notification(subject: str, body: str):
    """Send an email notification via SMTP."""
    if not app_config.smtp_host or not app_config.smtp_to:
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = app_config.smtp_from
        msg["To"] = app_config.smtp_to
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(app_config.smtp_host, app_config.smtp_port) as server:
            if app_config.smtp_user and app_config.smtp_password:
                server.starttls()
                server.login(app_config.smtp_user, app_config.smtp_password)
            server.send_message(msg)

        logger.info(f"Email notification sent to {app_config.smtp_to}")
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")


def send_ntfy_notification(title: str, message: str, priority: str = "default"):
    """Send a notification via ntfy.sh."""
    if not app_config.ntfy_topic:
        return False

    try:
        url = f"{app_config.ntfy_url.rstrip('/')}/{app_config.ntfy_topic}"
        headers = {"Title": title, "Priority": priority or app_config.ntfy_priority, "Tags": "no_entry,security"}

        req = urllib.request.Request(url, data=message.encode("utf-8"), headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=10) as response:
            if 200 <= response.status < 300:
                logger.info(f"ntfy notification sent to topic {app_config.ntfy_topic}")
                return True
            else:
                logger.error(f"Failed to send ntfy notification: HTTP {response.status}")
    except Exception as e:
        logger.error(f"Error sending ntfy notification: {e}")
    return False


def send_test_notification() -> bool:
    """Send a test notification through all configured channels."""
    test_ip = "1.2.3.4 (TEST)"
    test_reason = "Dies ist eine Test-Benachrichtigung vom NPM Traffic Monitor."
    test_until = datetime.now(timezone.utc) + __import__("datetime").timedelta(hours=1)

    # Check if any channel is configured
    any_configured = any([
        app_config.webhook_url,
        app_config.telegram_bot_token and app_config.telegram_chat_id,
        app_config.ntfy_topic,
        app_config.smtp_host and app_config.smtp_to
    ])

    if not any_configured:
        logger.warning("Keine Benachrichtigungskanäle für den Test konfiguriert.")
        return False

    # Force notify_on_block to True for the test
    original_setting = app_config.notify_on_block
    app_config.notify_on_block = True
    try:
        success = send_notification(test_ip, test_reason, test_until)
        return success
    except Exception as e:
        logger.error(f"Kritischer Fehler beim Senden des Test-Alerts: {e}")
        return False
    finally:
        app_config.notify_on_block = original_setting

def send_notification(ip: str, reason: str, block_until: datetime):
    """Send a notification via all configured channels."""
    if not app_config.notify_on_block:
        return False

    success = False

    # Common message parts
    title = "🚫 IP Blocked"
    description = f"IP Address: {ip}\nReason: {reason}\nBlocked Until: {block_until.strftime('%Y-%m-%d %H:%M:%S')}"

    # 1. ntfy.sh (High priority)
    if app_config.ntfy_topic:
        if send_ntfy_notification(title, description, "high"):
            success = True

    # 2. Webhook (Discord/Slack)
    if app_config.webhook_url:
        try:
            # Discord format (rich embed)
            formatted_desc = (
                f"**IP Address:** `{ip}`\n"
                f"**Reason:** {reason}\n"
                f"**Blocked Until:** {block_until.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if "discord.com" in app_config.webhook_url:
                payload = {
                    "embeds": [
                        {
                            "title": title,
                            "description": formatted_desc,
                            "color": 15158332,  # Red
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "footer": {"text": "NPM Monitor Alert"},
                        }
                    ]
                }
            else:
                payload = {"text": f"*{title}*\n{formatted_desc}"}

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                app_config.webhook_url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "NPM-Monitor"},
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if 200 <= response.status < 300:
                    success = True
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")

    # 3. Telegram
    if app_config.telegram_bot_token and app_config.telegram_chat_id:
        try:
            telegram_msg = (
                f"<b>{title}</b>\n\n"
                f"IP: <code>{ip}</code>\n"
                f"Grund: {reason}\n"
                f"Sperre bis: {block_until.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            telegram_url = f"https://api.telegram.org/bot{app_config.telegram_bot_token}/sendMessage"
            payload = {"chat_id": app_config.telegram_chat_id, "text": telegram_msg, "parse_mode": "HTML"}

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                telegram_url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "NPM-Monitor"},
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if 200 <= response.status < 300:
                    success = True
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")

    return success
