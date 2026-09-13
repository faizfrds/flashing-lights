"""Generic Webhook and Discord notification dispatcher.

Pushes structured JSON payloads to downstream APIs (e.g. disaster management dashboards)
or formatted Discord webhook embeds.
"""

import logging
from typing import List, Optional, Dict, Any
import requests

from core.alert_engine import AlertHotspot

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """Dispatches webhook payloads and Discord alerts."""

    def __init__(self, discord_url: Optional[str] = None, custom_url: Optional[str] = None):
        self.discord_url = discord_url
        self.custom_url = custom_url

    def send_discord_alert(self, hotspot: AlertHotspot) -> bool:
        """Pushes a rich embed message to a Discord webhook channel."""
        if not self.discord_url:
            return False

        color = 0xE74C3C if hotspot.severity == "CRITICAL" else 0xE67E22

        embed = {
            "title": f"🚨 FLASH FLOOD ALERT: {hotspot.regency}, {hotspot.province}",
            "description": f"Flash flood risk threshold exceeded in **{hotspot.district or hotspot.regency}**.",
            "color": color,
            "fields": [
                {"name": "Status", "value": hotspot.severity, "inline": True},
                {"name": "24h Rainfall", "value": f"{hotspot.estimated_rainfall_mm:.1f} mm", "inline": True},
                {"name": "Susceptibility Index", "value": f"{hotspot.susceptibility_index:.1f} / 100", "inline": True},
                {"name": "Cluster Area", "value": f"{hotspot.area_hectares:.1f} ha", "inline": True},
                {"name": "Event ID", "value": hotspot.hotspot_id, "inline": True},
                {"name": "Detected At", "value": hotspot.timestamp, "inline": True},
            ],
            "footer": {"text": "Indonesia FFEWS | GEE Automated Monitor"},
        }

        payload = {
            "username": "Indonesia Flash Flood Sentinel",
            "embeds": [embed],
        }

        try:
            resp = requests.post(self.discord_url, json=payload, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to transmit Discord webhook: {e}")
            return False

    def send_custom_webhook(self, hotspots: List[AlertHotspot]) -> bool:
        """Sends raw JSON payload of all active hotspots to an external API endpoint."""
        if not self.custom_url:
            return False

        payload = {
            "system": "Indonesia-FFEWS",
            "total_alerts": len(hotspots),
            "alerts": [h.to_dict() for h in hotspots],
        }

        try:
            resp = requests.post(self.custom_url, json=payload, timeout=10)
            return resp.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"Failed to post to custom webhook: {e}")
            return False

