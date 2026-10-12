"""
State 03: USD/JPY Carry & StatArb Pod (USDJPY H4).
Exploits US-Japan interest rate yield curve differentials, carry trade roll yield,
and mean-reversion around fair-value purchasing power parity (PPP).
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from ..base_pod import BaseStatePod, StateTradeProposal


class USDJPYCarryPod(BaseStatePod):
    """
    Sovereign State 03: USD/JPY Carry Trade & Interest Rate Differential Pod.
    """

    def __init__(self, allocated_capital: float = 200_000.0):
        super().__init__(
            state_id="STATE_03",
            state_name="State of USD/JPY Carry & Mean-Revert",
            primary_asset="USDJPY",
            strategy_style="StatArb Carry",
            timeframe="H4",
            allocated_capital=allocated_capital
        )

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        us_yield_10y: float = 4.25,
        jp_yield_10y: float = 0.85,
        account_equity: float = 1000.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on US-Japan 10Y sovereign bond yield differential.
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

        yield_differential = us_yield_10y - jp_yield_10y
        close = market_df["close"].values
        ma20 = float(np.mean(close[-20:]))
        current_price = close[-1]
        dist_ma_pct = (current_price - ma20) / ma20

        # Carry trading decision rules
        # Widening yield gap + not excessively overextended above MA20 -> Strong Long Carry
        if yield_differential > 2.50 and dist_ma_pct < 0.03:
            action = "BUY"
            rationale = f"Positive Carry Yield Spread ({round(yield_differential, 2)}%), Price near MA20"
            confidence = 0.72
        elif yield_differential < 1.0 or dist_ma_pct > 0.05:
            action = "SELL"
            rationale = f"Negative Carry Divergence or Mean-Reversion Overbought (Dist={round(dist_ma_pct*100, 2)}%)"
            confidence = 0.65
        else:
            action = "HOLD"
            rationale = "Carry differential in equilibrium; no directional skew."
            confidence = 0.50

        current_price = float(close[-1])
        effective_lots = self.calculate_risk_parity_lot(
            account_equity=account_equity,
            current_price=current_price,
            atr=abs(current_price - ma20),
            risk_fraction=0.005,
        )

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=effective_lots if action != "HOLD" else 0.0,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD"
        )
