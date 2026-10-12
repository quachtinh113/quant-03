"""Fleet Telemetry: Production Monitoring, Heartbeat, and Push Alerts.

Implements architectural and operations best practices:
1. Awesome-Selfhosted (Direct Telegram Bot & Discord Webhook alerting, no SaaS dependency).
2. The Book of Secret Knowledge (Process diagnostics, socket latency, dead-man-switch heartbeats).
3. Awesome-Python (Resilient, non-blocking fail-safe design, structured JSONL audit trail).
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("fleet_telemetry")


@dataclass
class HeartbeatState:
    """Snapshot of bot lifecycle and host system metrics."""
    bot_id: str
    timestamp_utc: str
    status: str
    last_symbol: str
    last_action: str
    pnl_session: float = 0.0
    open_positions: int = 0
    latency_ms: float = 0.0
    extra: Dict[str, Any] = None


class TelemetryNotifier:
    """Dispatches asynchronous alerts to Telegram and Discord with zero 3rd-party dependencies."""

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
    ):
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.discord_webhook = discord_webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    def send_telegram(self, message: str, parse_mode: str = "HTML", timeout: float = 5.0) -> bool:
        """Sends message via Telegram Bot API."""
        if not self.telegram_token or not self.telegram_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "QuantFleetBot/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Telegram notification failed (fail-safe bypassed): {e}")
            return False

    def send_discord(self, title: str, description: str, color: int = 0x3498DB, timeout: float = 5.0) -> bool:
        """Sends rich embed via Discord Webhook."""
        if not self.discord_webhook:
            return False

        payload = {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "footer": {"text": "Quant Fleet Telemetry Desk"}
                }
            ]
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.discord_webhook,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "QuantFleetBot/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.warning(f"Discord notification failed (fail-safe bypassed): {e}")
            return False

    def broadcast_critical_alert(self, subject: str, body: str) -> None:
        """Broadcasts high-priority alert across all configured channels."""
        tg_text = f"🚨 <b>[{subject}]</b>\n\n{body}"
        self.send_telegram(tg_text)
        self.send_discord(title=f"🚨 {subject}", description=body, color=0xE74C3C)


class FleetHeartbeat:
    """Maintains dead-man-switch heartbeats and system latency checks."""

    def __init__(self, bot_id: str, logs_dir: Optional[str] = None):
        self.bot_id = bot_id
        if logs_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent / "logs"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.logs_dir = base_dir
        else:
            self.logs_dir = Path(logs_dir)
            self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.heartbeat_file = self.logs_dir / f"heartbeat_{self.bot_id}.json"
        self.audit_log_file = self.logs_dir / "fleet_audit.jsonl"

    def measure_socket_latency(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> float:
        """Measures network TCP socket round-trip time in milliseconds."""
        t0 = time.perf_counter()
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            latency = (time.perf_counter() - t0) * 1000.0
            return round(latency, 2)
        except Exception:
            return 999.0

    def beat(
        self,
        status: str = "HEALTHY",
        symbol: str = "N/A",
        action: str = "CYCLE_CHECK",
        pnl: float = 0.0,
        open_positions: int = 0,
        deadman_webhook: Optional[str] = None,
    ) -> HeartbeatState:
        """Writes local heartbeat state and optionally pings deadman URL."""
        latency = self.measure_socket_latency()
        state = HeartbeatState(
            bot_id=self.bot_id,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            status=status,
            last_symbol=symbol,
            last_action=action,
            pnl_session=pnl,
            open_positions=open_positions,
            latency_ms=latency
        )

        # 1. Update local JSON heartbeat for Uptime monitoring / dashboard
        try:
            with open(self.heartbeat_file, "w", encoding="utf-8") as f:
                json.dump(asdict(state), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist heartbeat file: {e}")

        # 2. Append to structured JSONL audit trail
        try:
            with open(self.audit_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(state)) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

        # 3. Deadman switch URL ping (e.g. Healthchecks.io / Uptime Kuma)
        if deadman_webhook:
            try:
                req = urllib.request.Request(deadman_webhook, headers={"User-Agent": f"QuantHeartbeat/{self.bot_id}"})
                urllib.request.urlopen(req, timeout=3.0)
            except Exception as e:
                logger.warning(f"Deadman switch ping failed: {e}")

        return state
