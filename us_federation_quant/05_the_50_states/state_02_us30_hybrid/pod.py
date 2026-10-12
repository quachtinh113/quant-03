"""
State 02: Dow Jones Hybrid Momentum Pod (US30 H1).
Combines Time Series Momentum (TSMOM), Lo-MacKinlay Variance Ratio regime filter,
and Federal Reserve monetary policy alignment.
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

import importlib
from ..base_pod import BaseStatePod, StateTradeProposal

_mit_mod = importlib.import_module("us_federation_quant.01_congress_alpha.mit_dalio_foundation.mit_matrix_compensator")
MITMatrixCompensator = _mit_mod.MITMatrixCompensator


class US30HybridPod(BaseStatePod):
    """
    Sovereign State 02: US30 Equity Index Trend & Macro Momentum Pod.
    """

    def __init__(self, allocated_capital: float = 200_000.0):
        super().__init__(
            state_id="STATE_02",
            state_name="State of Dow Jones Momentum",
            primary_asset="US30",
            strategy_style="TSMOM Hybrid Momentum",
            timeframe="H1",
            allocated_capital=allocated_capital
        )

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        fed_stance: str = "NEUTRAL",
        account_equity: float = 1000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on Lo-MacKinlay Variance Ratio, FED macro stance,
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

        if len(market_df) < 25:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="Insufficient bar history for VR calculation.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="INSUFFICIENT_DATA"
            )

        close = market_df["close"].values
        vr_audit = MITMatrixCompensator.lo_mackinlay_variance_ratio(close[-25:], q=5)
        momentum_10 = (close[-1] - close[-10]) / close[-10]

        # Decision rules
        is_uptrend = momentum_10 > 0.002 and vr_audit.market_regime != "MEAN_REVERTING"
        is_downtrend = momentum_10 < -0.002 and vr_audit.market_regime != "MEAN_REVERTING"

        # Continuous Carver forecast in [-20.0, +20.0]
        raw_forecast = (momentum_10 / 0.005) * 12.0
        if vr_audit.market_regime == "MEAN_REVERTING":
            raw_forecast *= 0.3
        forecast = float(np.clip(raw_forecast, -20.0, 20.0))

        if is_uptrend:
            if "TIGHTENING" in fed_stance.upper() or "QT" in fed_stance.upper():
                action = "HOLD"
                forecast = 0.0
                rationale = "Bullish momentum blocked by Federal Reserve Quantitative Tightening (QT)."
                confidence = 0.40
            else:
                action = "BUY"
                forecast = max(2.5, forecast)
                rationale = f"US30 Strong Momentum Trend (VR={round(vr_audit.variance_ratio, 2)}), Macro={fed_stance}"
                confidence = 0.75

        elif is_downtrend:
            action = "SELL"
            forecast = min(-2.5, forecast)
            rationale = f"US30 Bearish Momentum Breakdown (VR={round(vr_audit.variance_ratio, 2)})"
            confidence = 0.75

        else:
            action = "HOLD"
            forecast = 0.0
            rationale = f"US30 in Random Walk / Consolidation (VR={round(vr_audit.variance_ratio, 2)})"
            confidence = 0.50

        current_price = float(close[-1])
        effective_atr = abs(close[-1] - close[-10]) if len(close) >= 10 else 200.0

        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=effective_atr,
                contract_size=1.0,
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
