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
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on US-Japan 10Y sovereign bond yield differential
        and Carver continuous forecasting with volatility budgeting and position buffering.
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

        # Continuous Carver forecast in [-20.0, +20.0]
        raw_forecast = ((yield_differential - 1.75) * 6.0) - (dist_ma_pct / 0.03 * 10.0)
        forecast = float(np.clip(raw_forecast, -20.0, 20.0))

        # Carry trading decision rules
        # Widening yield gap + not excessively overextended above MA20 -> Strong Long Carry
        if yield_differential > 2.50 and dist_ma_pct < 0.03:
            action = "BUY"
            forecast = max(2.5, forecast)
            rationale = f"Positive Carry Yield Spread ({round(yield_differential, 2)}%), Price near MA20"
            confidence = 0.72
        elif yield_differential < 1.0 or dist_ma_pct > 0.05:
            action = "SELL"
            forecast = min(-2.5, forecast)
            rationale = f"Negative Carry Divergence or Mean-Reversion Overbought (Dist={round(dist_ma_pct*100, 2)}%)"
            confidence = 0.65
        else:
            action = "HOLD"
            forecast = 0.0
            rationale = "Carry differential in equilibrium; no directional skew."
            confidence = 0.50

        effective_atr = abs(current_price - ma20) if abs(current_price - ma20) > 0 else (current_price * 0.005)

        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=effective_atr,
                contract_size=100_000.0,
            )
            raw_lots = carver_sizing["raw_lots"]
            effective_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=effective_atr,
                risk_fraction=0.005,
            )
            effective_lots = raw_lots
            is_buffered = False
        else:
            raw_lots = 0.0
            effective_lots = 0.0
            is_buffered = False

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=effective_lots,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD",
            carver_forecast=round(forecast, 2),
            raw_lots=raw_lots,
            buffered_lots=effective_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )
