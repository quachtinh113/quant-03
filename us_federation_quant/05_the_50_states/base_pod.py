"""
Base State Strategy Pod for The 50 States Fleet.
Provides autonomous lifecycle management for sovereign quantitative trading pods:
- State sovereignty and localized balance sheet.
- Localized Drawdown Ladder:
    - Drawdown <= -3%: De-leverage penalty (capital_multiplier = 0.50).
    - Drawdown <= -5%: Constitutional Quarantine (trading halted, quarantined = True).
- Direct liaison with Congress Alpha, Supreme Court, and Executive Order Router.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np
import pandas as pd

from .state_registry import StatePod


@dataclass
class StateTradeProposal:
    """A trade proposal submitted by a sovereign state pod."""
    state_id: str
    asset: str
    action: str  # "BUY", "SELL", "HOLD"
    target_lots: float
    strategy_style: str
    rationale: str
    confidence: float
    is_valid: bool
    rejection_reason: Optional[str] = None


class BaseStatePod(StatePod):
    """
    Autonomous Strategy Pod with localized risk governance and trading logic.
    """

    def __init__(
        self,
        state_id: str,
        state_name: str,
        primary_asset: str,
        strategy_style: str,
        timeframe: str,
        allocated_capital: float = 200_000.0,
        deleveraging_drawdown_threshold: float = -0.03, # -3%
        quarantine_drawdown_threshold: float = -0.05    # -5%
    ):
        super().__init__(
            state_id=state_id,
            state_name=state_name,
            primary_asset=primary_asset,
            strategy_style=strategy_style,
            timeframe=timeframe,
            allocated_capital=allocated_capital,
            local_drawdown=0.0,
            is_active=True
        )
        self.deleveraging_drawdown_threshold = deleveraging_drawdown_threshold
        self.quarantine_drawdown_threshold = quarantine_drawdown_threshold
        self.is_quarantined: bool = False
        self.capital_multiplier: float = 1.0
        self.trade_history: List[Dict[str, Any]] = []

    def update_performance(self, pnl_pct: float) -> bool:
        """
        Updates local performance and enforces the institutional drawdown ladder.
        - Level 1: Drawdown <= -3% -> cuts capital/leverage by 50%
        - Level 2: Drawdown <= -5% -> activates full quarantine
        """
        if pnl_pct < 0:
            self.local_drawdown += pnl_pct
        else:
            self.local_drawdown = min(0.0, self.local_drawdown + pnl_pct)

        # Drawdown Ladder Enforcement
        if self.local_drawdown <= self.quarantine_drawdown_threshold:
            self.is_active = False
            self.is_quarantined = True
            self.capital_multiplier = 0.0
            return False
        elif self.local_drawdown <= self.deleveraging_drawdown_threshold:
            self.capital_multiplier = 0.50
        else:
            self.capital_multiplier = 1.0

        return True

    def reinstate(self, reset_drawdown: bool = True):
        """Reinstates a quarantined state pod after audit and reset."""
        self.is_active = True
        self.is_quarantined = False
        self.capital_multiplier = 1.0
        if reset_drawdown:
            self.local_drawdown = 0.0

    def calculate_risk_parity_lot(
        self,
        account_equity: float = 1000.0,
        current_price: float = 2000.0,
        atr: Optional[float] = None,
        risk_fraction: float = 0.005,
    ) -> float:
        """
        Dynamic Risk Parity position sizing for sovereign state pods:
        Calculates safe lot size calibrated to account equity ($1,000 retail vs $250k institutional).
        Enforces local drawdown ladder de-leveraging.
        """
        if account_equity <= 0:
            return 0.01

        clean_asset = self.primary_asset.upper().replace("M", "")
        if "XAU" in clean_asset or "GOLD" in clean_asset:
            contract_size = 100.0
            max_lot = 0.05 if account_equity <= 5000 else (0.15 if account_equity <= 25000 else 5.0)
        elif "US30" in clean_asset or "US500" in clean_asset or "USTEC" in clean_asset or "BTC" in clean_asset:
            contract_size = 1.0
            max_lot = 0.10 if account_equity <= 5000 else (0.60 if account_equity <= 25000 else 5.0)
        else:  # FX Pairs
            contract_size = 100_000.0
            max_lot = 0.05 if account_equity <= 5000 else (0.15 if account_equity <= 25000 else 5.0)


        # Target Dollar Risk budget (default 0.5% of equity = $5 on $1000)
        target_risk_usd = max(1.0, account_equity * risk_fraction)

        # Volatility estimation
        effective_atr = atr if (atr and atr > 0) else (current_price * 0.005)
        dollar_risk_per_lot = effective_atr * contract_size * 1.5

        if dollar_risk_per_lot > 0:
            raw_lot = target_risk_usd / dollar_risk_per_lot
        else:
            raw_lot = 0.01

        # Apply state pod capital multiplier (Drawdown Ladder)
        effective_lot = raw_lot * self.capital_multiplier

        # Normalize and clamp to broker min (0.01) and max_lot
        final_lot = max(0.01, min(round(effective_lot, 2), max_lot))
        return final_lot

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        account_equity: float = 10000.0
    ) -> StateTradeProposal:
        """
        Default quantitative strategy for sovereign state pods:
        Bollinger Band Mean-Reversion & Volatility Breakout Filter.
        """
        if not self.is_active or self.is_quarantined:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="State is quarantined or inactive.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="STATE_QUARANTINED"
            )

        if len(market_df) < 20:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="Insufficient bar history.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="INSUFFICIENT_DATA"
            )

        close = market_df["close"].values
        current_price = float(close[-1])
        ma20 = float(np.mean(close[-20:]))
        std20 = float(np.std(close[-20:]))

        upper_band = ma20 + 2.0 * std20
        lower_band = ma20 - 2.0 * std20

        if current_price > upper_band:
            action = "SELL"
            rationale = f"Overbought Reversion Signal (Price: {current_price:.2f} > Upper: {upper_band:.2f})"
            confidence = 0.65
        elif current_price < lower_band:
            action = "BUY"
            rationale = f"Oversold Reversion Signal (Price: {current_price:.2f} < Lower: {lower_band:.2f})"
            confidence = 0.65
        else:
            action = "HOLD"
            rationale = f"Price in equilibrium [{lower_band:.2f} - {upper_band:.2f}]"
            confidence = 0.50

        target_lots = self.calculate_risk_parity_lot(
            account_equity=account_equity,
            current_price=current_price,
            atr=std20 if std20 > 0 else current_price * 0.005,
            risk_fraction=0.005,
        )

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=target_lots if action != "HOLD" else 0.0,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD"
        )

