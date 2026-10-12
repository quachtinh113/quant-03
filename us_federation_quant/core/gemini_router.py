"""Gemini Smart Router & Token Optimizer.

Implements architectural and LLM cost-efficiency best practices:
1. RouteLLM & LiteLLM (Complexity classification, Model Cascading, Fallbacks).
2. LLMLingua (Prompt compression, whitespace & redundancy stripping).
3. Budget Caps & Token Accounting (Daily token limits, cost tracking in USD).
4. Zero-Waste Structured Output (JSON enforcement, eliminating conversational fluff).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("gemini_router")


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
            base_dir = Path(__file__).resolve().parent.parent.parent / "logs"
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
                    logger.warning(f"Failed to read token budget file: {e}")

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
            logger.error(f"Failed to persist token budget: {e}")

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
                logger.critical(
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
                logger.warning("google-generativeai library not installed. Running in mock/dry-run mode.")

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
                logger.warning(
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
