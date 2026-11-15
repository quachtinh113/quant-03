"""l6_telemetry: tầng gộp từ audit_logger.py, fleet_telemetry.py, gemini_router.py."""
from __future__ import annotations

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re
import threading
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


# ====================================================================================================
# core/audit_logger.py  —  Unified Quant Fleet — Central Audit Logger
# ====================================================================================================



_logger = None

def setup_logger(log_dir: str = None, log_level: str = "INFO") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    if log_dir is None:
        log_path = Path(__file__).resolve().parent.parent / "logs"
    else:
        log_path = Path(log_dir)
        if not log_path.is_absolute():
            log_path = Path(__file__).resolve().parent.parent / log_dir

    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "us_federation_quant.log"

    level = getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger("USFederationQuant")
    logger.setLevel(level)
    logger.propagate = False
    logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (ensure utf-8 on Windows)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _logger = logger
    return _logger

def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger



# ====================================================================================================
# core/fleet_telemetry.py  —  Fleet Telemetry: Production Monitoring, Heartbeat, and Push Alerts.
# ====================================================================================================




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
            base_dir = Path(__file__).resolve().parent.parent / "logs"
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


# ====================================================================================================
# core/gemini_router.py  —  Gemini Smart Router & Token Optimizer.
# ====================================================================================================




logger__gemini_router = logging.getLogger("gemini_router")


class TaskTier(str, Enum):
    """Model tier matching computational and reasoning cost."""
    LIGHT = "light"      # Gemini 1.5 Flash / Flash-Lite: Cheap, ultra-fast, sentiment, parse
    HEAVY = "heavy"      # Gemini 1.5 Pro / Thinking: Deep math, architecture, complex refactor
    AUTO = "auto"        # Dynamically classified based on prompt length, complexity & intent


class BudgetExceededError(Exception):
    """Raised when daily token or cost budget limit is breached."""
    pass


@dataclass
class ModelCostProfile:
    """Pricing in USD per 1M tokens."""
    prompt_cost_per_m: float
    completion_cost_per_m: float


# Official approximate pricing per 1M tokens
MODEL_PRICING: Dict[str, ModelCostProfile] = {
    "gemini-1.5-flash": ModelCostProfile(prompt_cost_per_m=0.075, completion_cost_per_m=0.30),
    "gemini-1.5-pro": ModelCostProfile(prompt_cost_per_m=1.25, completion_cost_per_m=5.00),
    "mock-model": ModelCostProfile(prompt_cost_per_m=0.0, completion_cost_per_m=0.0),
}


class PromptCompressor:
    """LLMLingua-inspired lightweight prompt compressor.
    
    Eliminates redundant whitespace, duplicate log rows, and fluff to save 20-40% tokens.
    """

    @staticmethod
    def compress(text: str, max_repeated_lines: int = 2) -> str:
        if not text:
            return ""

        # 1. Normalize multiple empty lines to at most single empty line
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 2. Collapse runs of horizontal spaces
        text = re.sub(r"[ \t]+", " ", text)

        # 3. Deduplicate consecutive repetitive lines (e.g. repeated logs or tick lines)
        lines = text.split("\n")
        deduped: List[str] = []
        last_line: Optional[str] = None
        repeat_count = 0

        for line in lines:
            trimmed = line.strip()
            if trimmed == last_line and trimmed != "":
                repeat_count += 1
                if repeat_count <= max_repeated_lines:
                    deduped.append(line)
            else:
                last_line = trimmed
                repeat_count = 1
                deduped.append(line)

        return "\n".join(deduped).strip()


class TokenBudgetTracker:
    """Thread-safe persistent tracker for token usage and USD costs."""

    def __init__(self, budget_file: Optional[str] = None, max_daily_usd: float = 5.0):
        if budget_file is None:
            base_dir = Path(__file__).resolve().parent.parent / "logs"
            base_dir.mkdir(parents=True, exist_ok=True)
            budget_file = str(base_dir / "gemini_token_budget.json")

        self.budget_file = Path(budget_file)
        self.max_daily_usd = max_daily_usd
        self._lock = threading.Lock()
        self._today_cache: Dict[str, Any] = {}
        self._load()

    def _today_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load(self) -> None:
        with self._lock:
            today = self._today_str()
            if self.budget_file.exists():
                try:
                    with open(self.budget_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("date") == today:
                            self._today_cache = data
                            return
                except Exception as e:
                    logger__gemini_router.warning(f"Failed to read token budget file: {e}")

            self._today_cache = {
                "date": today,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_cost_usd": 0.0,
                "requests_count": 0,
            }
            self._save()

    def _save(self) -> None:
        try:
            with open(self.budget_file, "w", encoding="utf-8") as f:
                json.dump(self._today_cache, f, indent=2)
        except Exception as e:
            logger__gemini_router.error(f"Failed to persist token budget: {e}")

    def record_usage(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Records token usage and increments accumulated cost. Returns cost of this request."""
        profile = MODEL_PRICING.get(model_name, MODEL_PRICING["gemini-1.5-flash"])
        cost = (prompt_tokens / 1_000_000 * profile.prompt_cost_per_m) + (
            completion_tokens / 1_000_000 * profile.completion_cost_per_m
        )

        with self._lock:
            today = self._today_str()
            if self._today_cache.get("date") != today:
                self._today_cache = {
                    "date": today,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_cost_usd": 0.0,
                    "requests_count": 0,
                }

            self._today_cache["prompt_tokens"] += prompt_tokens
            self._today_cache["completion_tokens"] += completion_tokens
            self._today_cache["total_cost_usd"] += cost
            self._today_cache["requests_count"] += 1
            self._save()

            if self._today_cache["total_cost_usd"] > self.max_daily_usd:
                logger__gemini_router.critical(
                    f"Daily Gemini budget breached! Used ${self._today_cache['total_cost_usd']:.4f} > limit ${self.max_daily_usd}"
                )

        return cost

    def check_budget(self) -> None:
        """Raises BudgetExceededError if limit is reached."""
        with self._lock:
            if self._today_cache.get("total_cost_usd", 0.0) >= self.max_daily_usd:
                raise BudgetExceededError(
                    f"Daily Gemini spending cap of ${self.max_daily_usd:.2f} reached. Request halted to save costs."
                )

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._today_cache)


class GeminiSmartRouter:
    """Intelligent Router and Token Saver for Gemini API.
    
    1. Cascades from Fast/Light model to Heavy model on failure or high complexity.
    2. Compresses prompts before transmission.
    3. Enforces token budgets and tracks costs.
    """

    HEAVY_KEYWORDS = {
        "architect",
        "covariance",
        "eigenvalues",
        "random matrix",
        "derive",
        "factor neutrality",
        "kill switch",
        "black swan",
        "stress test",
        "refactor whole",
        "game theory",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        light_model_name: str = "gemini-1.5-flash",
        heavy_model_name: str = "gemini-1.5-pro",
        max_daily_usd: float = 5.0,
        budget_file: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.light_model_name = light_model_name
        self.heavy_model_name = heavy_model_name
        self.budget_tracker = TokenBudgetTracker(budget_file=budget_file, max_daily_usd=max_daily_usd)
        self.compressor = PromptCompressor()
        self._genai = None
        self._init_genai()

    def _init_genai(self) -> None:
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._genai = genai
            except ImportError:
                logger__gemini_router.warning("google-generativeai library not installed. Running in mock/dry-run mode.")

    def classify_complexity(self, prompt: str) -> TaskTier:
        """Deterministic heuristic classifier: decides whether prompt needs Light or Heavy model."""
        prompt_lower = prompt.lower()
        word_count = len(prompt.split())

        # If prompt is long or contains institutional quant/math keywords -> HEAVY
        if word_count > 600 or any(kw in prompt_lower for kw in self.HEAVY_KEYWORDS):
            return TaskTier.HEAVY

        return TaskTier.LIGHT

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        tier: TaskTier = TaskTier.AUTO,
        compress_prompt: bool = True,
        response_json: bool = False,
        max_output_tokens: Optional[int] = None,
        mock_handler: Optional[Callable[[str, str], str]] = None,
    ) -> Dict[str, Any]:
        """Routes prompt to appropriate model, applies compression and tracks expenditure.
        
        Returns dict with:
        - content: model reply
        - model_used: name of the model that served the response
        - cost_usd: cost incurred
        - compressed_saved_chars: characters saved by compression
        """
        # 1. Check budget cap
        self.budget_tracker.check_budget()

        # 2. Compress prompt
        original_len = len(prompt)
        processed_prompt = self.compressor.compress(prompt) if compress_prompt else prompt
        saved_chars = max(0, original_len - len(processed_prompt))

        # 3. Determine Model Tier
        target_tier = tier
        if target_tier == TaskTier.AUTO:
            target_tier = self.classify_complexity(processed_prompt)

        selected_model = self.heavy_model_name if target_tier == TaskTier.HEAVY else self.light_model_name

        # 4. Dispatch Generation with Cascade Fallback
        content = ""
        actual_model = selected_model

        try:
            content = self._call_model(
                model_name=selected_model,
                prompt=processed_prompt,
                system_instruction=system_instruction,
                response_json=response_json,
                max_output_tokens=max_output_tokens,
                mock_handler=mock_handler,
            )
        except Exception as primary_exc:
            # If Light model fails, cascade to Heavy model
            if selected_model == self.light_model_name:
                logger__gemini_router.warning(
                    f"Light model {selected_model} failed ({primary_exc}). "
                    f"Cascading fallback to Heavy model {self.heavy_model_name}..."
                )
                actual_model = self.heavy_model_name
                content = self._call_model(
                    model_name=actual_model,
                    prompt=processed_prompt,
                    system_instruction=system_instruction,
                    response_json=response_json,
                    max_output_tokens=max_output_tokens,
                    mock_handler=mock_handler,
                )
            else:
                raise primary_exc

        # 5. Token Accounting (approximate 4 chars per token if usage metadata unavailable)
        est_prompt_tokens = max(1, len(processed_prompt) // 4)
        est_completion_tokens = max(1, len(content) // 4)
        cost = self.budget_tracker.record_usage(actual_model, est_prompt_tokens, est_completion_tokens)

        return {
            "content": content,
            "model_used": actual_model,
            "tier_used": target_tier.value,
            "cost_usd": cost,
            "chars_saved": saved_chars,
            "prompt_tokens_est": est_prompt_tokens,
            "completion_tokens_est": est_completion_tokens,
        }

    def _call_model(
        self,
        model_name: str,
        prompt: str,
        system_instruction: Optional[str],
        response_json: bool,
        max_output_tokens: Optional[int],
        mock_handler: Optional[Callable[[str, str], str]] = None,
    ) -> str:
        """Internal execution handler supporting real Gemini API and test mocks."""
        if mock_handler:
            return mock_handler(model_name, prompt)

        if not self._genai:
            return f"[MOCK_RESPONSE from {model_name}]: Received prompt ({len(prompt)} chars)."

        generation_config: Dict[str, Any] = {}
        if response_json:
            generation_config["response_mime_type"] = "application/json"
        if max_output_tokens:
            generation_config["max_output_tokens"] = max_output_tokens

        model = self._genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction,
            generation_config=generation_config if generation_config else None,
        )
        resp = model.generate_content(prompt)
        return resp.text
