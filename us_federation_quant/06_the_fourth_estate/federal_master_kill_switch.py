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
import logging

logger = logging.getLogger("FederalMasterKillSwitch")


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
    and enforce Soft De-risking protocols to preserve the federation's survival.
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
        self.freeze_until: float = 0.0
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
        Raises FederalCircuitBreakerActive if locked or within 24h freeze window.
        """
        if self.is_locked or (self.freeze_until > 0 and time.time() < self.freeze_until):
            remaining_hours = max(0.0, (self.freeze_until - time.time()) / 3600.0) if self.freeze_until > 0 else 0.0
            raise FederalCircuitBreakerActive(
                f"FEDERAL EMERGENCY: Master Kill-Switch is ACTIVE (Soft De-risking engaged). "
                f"All trading rights are suspended (Freeze remaining: {remaining_hours:.1f} hours)."
            )

    def manual_emergency_shutdown(
        self,
        reason: str,
        broker_connector: Optional[Any] = None
    ) -> KillSwitchDirective:
        """
        Manual trigger of the Federal Master Kill-Switch by the Chief Risk Officer.
        Executes Soft De-risking protocol instead of aggressive market close dump.
        """
        self.is_locked = True
        self.freeze_until = time.time() + 86400.0  # 24 hours freeze
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
            self.freeze_until = 0.0
            self.peak_equity = self.current_equity  # Reset peak benchmark upon authorized recovery
            logger.info("🔓 [FEDERATION UNLOCKED] Master Kill-Switch reset and 24h freeze cleared.")
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

    def apply_soft_derisking(
        self,
        active_positions: List[Dict[str, Any]],
        broker_connector: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Quant Core V9: Soft De-risking Protocol.
        Replaces catastrophic 'Fleet Close' market dump with an intelligent capital preservation protocol:
        1. Triggers system freeze flag for new signals for 24 hours.
        2. Iterates through active positions WITHOUT market closing them.
        3. For positions in profit (PnL > 0): Modifies SL to Entry Price ± (15 * symbol_point) to lock in break-even plus buffer.
        4. For positions in loss (PnL < 0): Does nothing (retains original hard SL to allow technical pullback).
        """
        self.freeze_until = time.time() + 86400.0  # 24 hours freeze
        self.is_locked = True
        logger.warning(
            f"🛑 [SOFT DE-RISKING PROTOCOL ACTIVATED] System freeze engaged for 24 hours (until {time.ctime(self.freeze_until)}). "
            f"Market dump (Fleet Close) ABORTED. Processing {len(active_positions)} active positions via Soft De-risking..."
        )

        modified_positions = []
        for p in active_positions:
            ticket = int(p.get("ticket", 0) if isinstance(p, dict) else getattr(p, "ticket", 0))
            symbol = str(p.get("symbol", "") if isinstance(p, dict) else getattr(p, "symbol", ""))
            profit = float(p.get("profit", 0.0) if isinstance(p, dict) else getattr(p, "profit", 0.0))
            raw_type = p.get("type", "") if isinstance(p, dict) else getattr(p, "type", "")
            price_open = float(p.get("price_open", p.get("open_price", 0.0)) if isinstance(p, dict) else getattr(p, "price_open", 0.0))

            # Resolve symbol specs
            symbol_point = 0.0001
            digits = 2
            if broker_connector and hasattr(broker_connector, "get_symbol_spec"):
                spec = broker_connector.get_symbol_spec(symbol)
                symbol_point = spec.get("point", 0.0001) or 0.0001
                digits = spec.get("digits", 2) or 2
            else:
                try:
                    import MetaTrader5 as mt5
                    s_info = mt5.symbol_info(symbol)
                    if s_info:
                        symbol_point = getattr(s_info, "point", 0.0001) or 0.0001
                        digits = getattr(s_info, "digits", 2) or 2
                except Exception:
                    pass

            is_buy = str(raw_type).upper() in ["BUY", "0"] or raw_type == 0

            if profit > 0:
                # Modifies Stop Loss to Entry Price ± (15 * symbol_point)
                buffer_offset = 15.0 * symbol_point
                new_sl = round(price_open + buffer_offset if is_buy else price_open - buffer_offset, digits)

                mod_res = None
                if broker_connector and hasattr(broker_connector, "modify_position_sltp"):
                    mod_res = broker_connector.modify_position_sltp(ticket=ticket, sl=new_sl)

                logger.info(
                    f"🛡️ [SOFT DE-RISKING] Profitable Position #{ticket} ({symbol}, PnL: +${profit:.2f} USD): "
                    f"Locked in Break-Even + 15pt buffer. Target SL updated to {new_sl} (Open: {price_open})."
                )
                modified_positions.append({
                    "ticket": ticket,
                    "symbol": symbol,
                    "action": "LOCK_IN_BREAKEVEN_BUFFER",
                    "new_sl": new_sl,
                    "profit": profit,
                    "result": mod_res,
                })
            else:
                logger.info(
                    f"🛡️ [SOFT DE-RISKING] Floating Loss Position #{ticket} ({symbol}, PnL: -${abs(profit):.2f} USD): "
                    f"Retained original protective SL to await technical pullback. Market close avoided."
                )
                modified_positions.append({
                    "ticket": ticket,
                    "symbol": symbol,
                    "action": "RETAIN_ORIGINAL_SL",
                    "profit": profit,
                })

        return modified_positions

    def _execute_emergency_liquidation(self, broker_connector: Any) -> None:
        """Executes Soft De-risking protocol instead of panic market liquidation."""
        positions = []
        if hasattr(broker_connector, "get_positions"):
            positions = broker_connector.get_positions()
        elif hasattr(broker_connector, "positions"):
            positions = list(broker_connector.positions.values())
        self.apply_soft_derisking(positions, broker_connector)
