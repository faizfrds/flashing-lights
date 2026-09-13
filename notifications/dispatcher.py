"""Unified notification dispatcher for all alert channels."""

import logging
from typing import List

from config import config
from core.alert_engine import AlertHotspot
from notifications.telegram import TelegramNotifier
from notifications.webhook import WebhookNotifier

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """Coordinates distribution of alerts across configured channels."""

    def __init__(self, cfg=config):
        self.cfg = cfg
        self.telegram = TelegramNotifier(cfg.telegram_bot_token, cfg.telegram_chat_id)
        self.webhook = WebhookNotifier(cfg.discord_webhook_url, cfg.custom_webhook_url)

    def dispatch(self, hotspots: List[AlertHotspot]) -> dict:
        """Dispatches hotspots across active channels and returns delivery summary."""
        summary = {
            "total_hotspots": len(hotspots),
            "telegram_delivered": 0,
            "discord_delivered": 0,
            "custom_webhook_delivered": False,
        }

        if not hotspots:
            logger.info("No hotspots to dispatch.")
            return summary

        # 1. Telegram
        if self.telegram.is_configured:
            delivered = self.telegram.broadcast_alerts(hotspots)
            summary["telegram_delivered"] = delivered

        # 2. Discord
        if self.webhook.discord_url:
            d_count = 0
            for h in hotspots:
                if self.webhook.send_discord_alert(h):
                    d_count += 1
            summary["discord_delivered"] = d_count

        # 3. Custom Webhook
        if self.webhook.custom_url:
            summary["custom_webhook_delivered"] = self.webhook.send_custom_webhook(hotspots)

        return summary

