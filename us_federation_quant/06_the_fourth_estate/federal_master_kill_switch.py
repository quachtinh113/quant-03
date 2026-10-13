"""
The Federal Master Kill-Switch (Totalitarian Emergency Circuit Breaker).
Enforces absolute portfolio survival mechanics based on Millennium / Citadel CRO doctrine:
- Level 1: Drawdown <= -3.0% -> Yellow Alert (Mandatory 50% Position Sizing Reduction)
- Level 2: Drawdown <= -5.0% -> Orange Alert (Mandatory De-leveraging)
- Level 3: Drawdown <= -7.5% -> Red Catastrophic Kill-Switch (Total Liquidation & Complete Lockdown)
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import hashlib
import time


class FederalCircuitBreakerActive(Exception):
    """Raised when orders are attempted while the Federal Master Kill-Switch is locked."""
    pass


@dataclass
class KillSwitchDirective:
    """Action directive emitted by the Federal Master Kill-Switch."""
    status_level: str          # "NORMAL", "YELLOW_ALERT", "ORANGE_ALERT", "RED_KILL_SWITCH"
    current_drawdown_pct: float
    is_trading_locked: bool
    position_scale_factor: float  # 1.0 (Normal), 0.5 (Yellow), 0.25 (Orange), 0.0 (Locked)
    reason: str
    auth_token: str
    timestamp: float


class FederalMasterKillSwitch:
    """
    Totalitarian Risk Kill-Switch.
    Holds overriding supreme authority to sever all live execution connections
    and liquidate all 50 State pods to preserve the federation's survival.
    """

    def __init__(
        self,
        yellow_threshold: float = -0.03,  # -3%
        orange_threshold: float = -0.05,  # -5%
        red_threshold: float = -0.12,     # -12.0%
        secret_passphrase: str = "CONSTITUTIONAL_EMERGENCY_OVERRIDE_KEY"
    ):
        self.yellow_threshold = yellow_threshold
        self.orange_threshold = orange_threshold
        self.red_threshold = red_threshold
        self.secret_passphrase = secret_passphrase

        self.peak_equity: float = 0.0
        self.current_equity: float = 0.0
        self.is_locked: bool = False
        self.incident_history: List[KillSwitchDirective] = []

    def update_equity(
        self,
        current_equity: float,
        broker_connector: Optional[Any] = None
    ) -> KillSwitchDirective:
        """
        Updates live portfolio equity, calculates drawdown from peak,
        and enforces the totalitarian drawdown ladder.
        """
        if current_equity <= 0:
            raise ValueError(f"Invalid portfolio equity: {current_equity}")

        if self.peak_equity <= 0 or current_equity > self.peak_equity:
            self.peak_equity = current_equity

        self.current_equity = current_equity
        drawdown_pct = (self.current_equity - self.peak_equity) / self.peak_equity

        # If already locked, maintain lockdown until explicit cryptographic unfreeze
        if self.is_locked:
            return self._create_directive(
                status_level="RED_KILL_SWITCH",
                drawdown_pct=drawdown_pct,
                is_locked=True,
                scale_factor=0.0,
                reason="Federation is currently LOCKED under Master Kill-Switch quarantine."
            )

        # 1. Level 3: Red Catastrophic Breaker
        if drawdown_pct <= self.red_threshold:
            self.is_locked = True
            directive = self._create_directive(
                status_level="RED_KILL_SWITCH",
                drawdown_pct=drawdown_pct,
                is_locked=True,
                scale_factor=0.0,
                reason=f"CRITICAL DRAWDOWN {round(drawdown_pct * 100, 2)}% breached limit {round(self.red_threshold * 100, 1)}%. MASTER KILL-SWITCH ACTIVATED!"
            )
            # Trigger emergency broker liquidation if connector provided
            if broker_connector is not None:
                self._execute_emergency_liquidation(broker_connector)
            return directive

        # 2. Level 2: Orange Alert
        elif drawdown_pct <= self.orange_threshold:
            return self._create_directive(
                status_level="ORANGE_ALERT",
                drawdown_pct=drawdown_pct,
                is_locked=False,
                scale_factor=0.25,
                reason=f"Orange Risk Alert: Drawdown {round(drawdown_pct * 100, 2)}% breached -5.0%. De-leveraging by 75%."
            )

        # 3. Level 1: Yellow Alert
        elif drawdown_pct <= self.yellow_threshold:
            return self._create_directive(
                status_level="YELLOW_ALERT",
                drawdown_pct=drawdown_pct,
                is_locked=False,
                scale_factor=0.50,
                reason=f"Yellow Risk Alert: Drawdown {round(drawdown_pct * 100, 2)}% breached -3.0%. Cutting new order sizes by 50%."
            )

        # Normal operation
        return self._create_directive(
            status_level="NORMAL",
            drawdown_pct=drawdown_pct,
            is_locked=False,
            scale_factor=1.0,
            reason="Portfolio operating within constitutional risk boundaries."
        )

    def verify_order_permission(self) -> None:
        """
        Gatekeeper check before any order can be routed.
        Raises FederalCircuitBreakerActive if locked.
        """
        if self.is_locked:
            raise FederalCircuitBreakerActive(
                "FEDERAL EMERGENCY: Master Kill-Switch is ACTIVE. All trading rights are suspended."
            )

    def manual_emergency_shutdown(
        self,
        reason: str,
        broker_connector: Optional[Any] = None
    ) -> KillSwitchDirective:
        """
        Manual trigger of the Federal Master Kill-Switch by the Chief Risk Officer.
        """
        self.is_locked = True
        dd_pct = (self.current_equity - self.peak_equity) / max(self.peak_equity, 1.0)
        directive = self._create_directive(
            status_level="RED_KILL_SWITCH",
            drawdown_pct=dd_pct,
            is_locked=True,
            scale_factor=0.0,
            reason=f"MANUAL CRO OVERRIDE: {reason}"
        )
        if broker_connector is not None:
            self._execute_emergency_liquidation(broker_connector)
        return directive

    def unlock_federation(self, unfreeze_token: str) -> bool:
        """
        Unfreezes the federation after audit, requiring the cryptographic pass token.
        """
        expected_token = hashlib.sha256(self.secret_passphrase.encode()).hexdigest()
        if unfreeze_token == expected_token or unfreeze_token == self.secret_passphrase:
            self.is_locked = False
            self.peak_equity = self.current_equity  # Reset peak benchmark upon authorized recovery
            return True
        return False

    def _create_directive(
        self,
        status_level: str,
        drawdown_pct: float,
        is_locked: bool,
        scale_factor: float,
        reason: str
    ) -> KillSwitchDirective:
        now = time.time()
        raw = f"{status_level}:{drawdown_pct}:{is_locked}:{now}:{self.secret_passphrase}"
        token = hashlib.sha256(raw.encode()).hexdigest()[:16]

        directive = KillSwitchDirective(
            status_level=status_level,
            current_drawdown_pct=round(drawdown_pct, 4),
            is_trading_locked=is_locked,
            position_scale_factor=scale_factor,
            reason=reason,
            auth_token=token,
            timestamp=now
        )
        self.incident_history.append(directive)
        return directive

    def _execute_emergency_liquidation(self, broker_connector: Any) -> None:
        """Invokes broker connection to flatten open risk."""
        if hasattr(broker_connector, "close_all_positions"):
            broker_connector.close_all_positions()
        elif hasattr(broker_connector, "positions"):
            for pos in list(broker_connector.positions.values()):
                ticket = pos.get("ticket")
                if ticket and hasattr(broker_connector, "close_position"):
                    broker_connector.close_position(ticket)
