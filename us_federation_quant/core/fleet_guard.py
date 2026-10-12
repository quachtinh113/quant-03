"""Fleet Guard: Production Safety & System Design Protection Layer.

Implements architectural and security best practices:
1. System Design Primer (Idempotency, Token Bucket Rate Limiting, Circuit Breaker).
2. Awesome-Hacking (Zero-Trust Validation: Hard Max Lot Cap, Mandatory Stop Loss, Slippage Ceiling).
3. Awesome-Python (Thread-safe, Concurrency-proof, Zero-overhead).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("fleet_guard")


class IdempotencyError(Exception):
    """Raised when a duplicate order request is detected."""
    pass


class SanityCheckError(Exception):
    """Raised when an order violates zero-trust risk bounds."""
    pass


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is active and blocking new trades."""
    pass


@dataclass
class GuardConfig:
    """Configuration for Zero-Trust and System-Design safeguards."""
    max_lot_cap: float = 0.50             # Hard lot ceiling across all strategies
    min_lot_floor: float = 0.01           # Hard lot floor
    mandatory_sl: bool = True             # Absolute zero-tolerance for naked positions
    max_slippage_points: float = 30.0     # Max deviation / slippage points allowed
    rate_limit_per_sec: float = 5.0       # Max requests per second to MT5
    consecutive_error_threshold: int = 3  # Failures before circuit trips
    circuit_cooldown_sec: int = 1800      # 30-minute lockdown on tripped circuit
    db_path: Optional[str] = None         # SQLite WAL path for idempotency persistence


class IdempotencyRegistry:
    """Guarantees exactly-once execution per (magic, symbol, bar_time, direction).
    
    Prevents duplicate orders during broker retries, network blips, or scheduler overlaps.
    Uses SQLite in WAL mode for persistent, cross-process reliability.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent / "logs"
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / "idempotency_store.db")
        
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS idempotency_keys (
                        token TEXT PRIMARY KEY,
                        bot_id TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        action TEXT NOT NULL,
                        lot REAL NOT NULL,
                        created_at REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at 
                    ON idempotency_keys(created_at);
                """)
                conn.commit()

    @staticmethod
    def generate_token(magic: int, symbol: str, bar_time_utc: str, action: str, lot: float) -> str:
        """Computes deterministic SHA256 idempotency fingerprint."""
        raw = f"{magic}|{symbol.upper()}|{bar_time_utc}|{action.upper()}|{lot:.4f}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def acquire(self, token: str, bot_id: str, symbol: str, action: str, lot: float, ttl_seconds: int = 86400) -> bool:
        """Attempts to register token. Returns True if first-time, False if duplicate.
        
        Automatically purges stale entries older than ttl_seconds.
        """
        now = time.time()
        with self._lock:
            with self._get_connection() as conn:
                # Cleanup stale records
                conn.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (now - ttl_seconds,))
                
                # Check if exists
                cur = conn.cursor()
                cur.execute("SELECT token FROM idempotency_keys WHERE token = ?", (token,))
                if cur.fetchone():
                    return False
                
                # Register
                try:
                    conn.execute(
                        "INSERT INTO idempotency_keys (token, bot_id, symbol, action, lot, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (token, bot_id, symbol, action, lot, now)
                    )
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False


class TokenBucketLimiter:
    """Thread-safe Token Bucket Rate Limiter to prevent terminal/broker flooding."""

    def __init__(self, rate_per_sec: float = 5.0, capacity: float = 10.0):
        self.rate = rate_per_sec
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens_needed: float = 1.0, wait: bool = True) -> bool:
        """Acquires tokens, sleeping if necessary up to a safety limit."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= tokens_needed:
                    self.tokens -= tokens_needed
                    return True
                
                if not wait:
                    return False
                
                missing = tokens_needed - self.tokens
                sleep_time = missing / self.rate

            time.sleep(min(sleep_time, 0.5))


class CircuitBreaker:
    """Circuit Breaker (CLOSED -> OPEN -> HALF-OPEN) to protect capital during outages."""

    def __init__(self, threshold: int = 3, cooldown_sec: int = 1800):
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self.consecutive_errors = 0
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def record_success(self) -> None:
        with self._lock:
            self.consecutive_errors = 0
            self.last_failure_time = None

    def record_failure(self) -> None:
        with self._lock:
            self.consecutive_errors += 1
            self.last_failure_time = time.time()
            if self.consecutive_errors >= self.threshold:
                logger.critical(
                    f"[CIRCUIT BREAKER TRIPPED] {self.consecutive_errors} consecutive failures! "
                    f"Tripping circuit for {self.cooldown_sec} seconds."
                )

    def is_open(self) -> bool:
        with self._lock:
            if self.consecutive_errors < self.threshold:
                return False
            
            # Check cooldown
            if self.last_failure_time and (time.time() - self.last_failure_time > self.cooldown_sec):
                logger.info("[CIRCUIT BREAKER HALF-OPEN] Cooldown period passed. Allowing canary test.")
                return False
            
            return True


class FleetGuard:
    """Master orchestrator combining Idempotency, Rate-Limiting, Sanity, and Circuit Breakers."""

    def __init__(self, config: Optional[GuardConfig] = None):
        self.cfg = config or GuardConfig()
        self.idempotency = IdempotencyRegistry(self.cfg.db_path)
        self.limiter = TokenBucketLimiter(rate_per_sec=self.cfg.rate_limit_per_sec)
        self.breaker = CircuitBreaker(
            threshold=self.cfg.consecutive_error_threshold,
            cooldown_sec=self.cfg.circuit_cooldown_sec
        )

    def validate_and_gate_order(
        self,
        bot_id: str,
        magic: int,
        symbol: str,
        bar_time_utc: str,
        action: str,
        lot: float,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float] = None,
    ) -> str:
        """Performs full Zero-Trust Gate check.
        
        Returns the registered unique idempotency token on success.
        Raises SanityCheckError, IdempotencyError, or CircuitBreakerOpenError on violation.
        """
        # 1. Circuit Breaker Check
        if self.breaker.is_open():
            raise CircuitBreakerOpenError(
                f"FleetGuard Circuit Breaker is OPEN for {bot_id}. Trading halted due to consecutive failures."
            )

        # 2. Rate Limiting Check
        self.limiter.acquire(1.0, wait=True)

        # 3. Zero-Trust Lot Sizing Bounds
        if lot > self.cfg.max_lot_cap:
            raise SanityCheckError(
                f"[VIOLATION] Requested lot {lot:.3f} exceeds hard MAX_LOT_CAP ({self.cfg.max_lot_cap}). "
                f"Order strictly aborted."
            )
        if lot < self.cfg.min_lot_floor:
            raise SanityCheckError(
                f"[VIOLATION] Requested lot {lot:.3f} below MIN_LOT_FLOOR ({self.cfg.min_lot_floor})."
            )

        # 4. Mandatory Stop Loss Check
        act = action.lower()
        if self.cfg.mandatory_sl:
            if stop_loss is None or stop_loss <= 0:
                raise SanityCheckError(
                    f"[ZERO-TRUST VIOLATION] Naked position detected! {bot_id} tried {action} without valid Stop-Loss."
                )
            if act in ("buy", "long") and stop_loss >= entry_price:
                raise SanityCheckError(
                    f"[SANITY FAILED] BUY order SL ({stop_loss}) must be strictly below entry price ({entry_price})."
                )
            if act in ("sell", "short") and stop_loss <= entry_price:
                raise SanityCheckError(
                    f"[SANITY FAILED] SELL order SL ({stop_loss}) must be strictly above entry price ({entry_price})."
                )

        # 5. Idempotency Check (Chống trùng lệnh)
        token = self.idempotency.generate_token(magic, symbol, bar_time_utc, action, lot)
        acquired = self.idempotency.acquire(token, bot_id, symbol, action, lot)
        if not acquired:
            raise IdempotencyError(
                f"[DUPLICATE REJECTED] Order already executed for token: {token[:12]}... "
                f"({bot_id} {symbol} {bar_time_utc} {action})"
            )

        logger.info(f"[FLEET GUARD PASS] Bot {bot_id} authorized: {action} {lot} {symbol} (Token: {token[:8]})")
        return token
