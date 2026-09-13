"""Telegram Bot alert notification dispatcher.

Sends formatted multilingual (Indonesian & English) emergency flood warnings
to designated Telegram channels, BPBD incident commander groups, or volunteer networks.
"""

import logging
from typing import List, Optional
import requests

from core.alert_engine import AlertHotspot

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Dispatches emergency flash flood notifications via Telegram Bot API."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def format_alert_message(self, hotspot: AlertHotspot) -> str:
        """Constructs an Indonesian + English formatted alert message."""
        severity_emoji = "🔴" if hotspot.severity == "CRITICAL" else "🟠"
        severity_label = "SIAGA 1 (KRITIS)" if hotspot.severity == "CRITICAL" else "WASPADA TINGGI"

        msg = (
            f"🚨 *PERINGATAN DINI BANJIR BANDANG / FLASH FLOOD ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{severity_emoji} *Status: {severity_label} ({hotspot.severity})*\n"
            f"🆔 *ID Kejadian:* `{hotspot.hotspot_id}`\n"
            f"⏰ *Waktu Terdeteksi:* `{hotspot.timestamp}`\n\n"
            f"📍 *WILAYAH TERDAMPAK (LOCATION):*\n"
            f"• Provinsi: *{hotspot.province}*\n"
            f"• Kabupaten/Kota: *{hotspot.regency}*\n"
        )
        if hotspot.district:
            msg += f"• Sub-DAS / Wilayah: *{hotspot.district}*\n"

        msg += (
            f"\n📊 *PARAMETER HIDRO-METEOROLOGI:*\n"
            f"• Curah Hujan 24 Jam: *{hotspot.estimated_rainfall_mm:.1f} mm* (Ekstrem)\n"
            f"• Indeks Kerentanan Lereng & Hutan: *{hotspot.susceptibility_index:.1f}/100*\n"
            f"• Luas Zona Bahaya: *{hotspot.area_hectares:.1f} Hektar*\n\n"
            f"⚠️ *REKOMENDASI MITIGASI BPBD / RELAWAN:*\n"
            f"1. Pantau debit air pada hulu sungai dan pintu air terdekat.\n"
            f"2. Bersiap evakuasi warga pada bantaran sungai dan lereng rawan longsor.\n"
            f"3. Siagakan posko tanggap darurat dan jalur evakuasi aman.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 *Sistem Deteksi Dini GEE - FFEWS Indonesia*"
        )
        return msg

    def send_hotspot_alert(self, hotspot: AlertHotspot) -> bool:
        """Sends a single hotspot alert to the configured chat."""
        if not self.is_configured:
            logger.info(f"[Telegram Notifier - Unconfigured] Alert simulated for {hotspot.regency} ({hotspot.hotspot_id})")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        text = self.format_alert_message(hotspot)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram alert successfully sent for {hotspot.hotspot_id}")
                return True
            else:
                logger.error(f"Telegram API responded with {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to transmit Telegram message: {e}")
            return False

    def broadcast_alerts(self, hotspots: List[AlertHotspot]) -> int:
        """Sends alerts for all detected hotspots."""
        count = 0
        for h in hotspots:
            if self.send_hotspot_alert(h):
                count += 1
        return count

