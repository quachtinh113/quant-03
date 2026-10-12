"""
State 01: Gold Microstructure Scalping Pod (XAUUSD M15).
Specializes in high-frequency order flow imbalance, extreme volatility filtering,
and Avellaneda-Stoikov spread capture on Gold.
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

import importlib
from ..base_pod import BaseStatePod, StateTradeProposal

_event_mod = importlib.import_module("us_federation_quant.01_congress_alpha.ml_engine.event_sampling")
SymmetricCUSUMFilter = _event_mod.SymmetricCUSUMFilter

_alpha_mod = importlib.import_module("us_federation_quant.01_congress_alpha.formulaic_alpha_fleet.formulaic_alphas_101")
FormulaicAlphas101 = _alpha_mod.FormulaicAlphas101


class GoldScalpPod(BaseStatePod):
    """
    Sovereign State 01: XAUUSD Microstructure Scalper.
    """

    def __init__(self, allocated_capital: float = 250_000.0):
        super().__init__(
            state_id="STATE_01",
            state_name="State of Gold Micro-Scalp",
            primary_asset="XAUUSD",
            strategy_style="Avellaneda-Stoikov Micro-Scalp",
            timeframe="M15",
            allocated_capital=allocated_capital
        )
        self.cusum_filter = SymmetricCUSUMFilter(threshold_multiplier=1.8, default_threshold=0.008)

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        account_equity: float = 1000.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on CUSUM structural events and Garman-Klass volatility.
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

        if len(market_df) < 15:
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

        close = market_df["close"]
        gk_vol = FormulaicAlphas101.calculate_garman_klass_volatility(market_df).iloc[-1]
        a101 = FormulaicAlphas101.alpha_101(market_df).iloc[-1]

        # Check structural CUSUM event
        cusum_res = self.cusum_filter.filter_events(close)
        latest_event_direction = cusum_res["event_directions"][-1] if cusum_res["event_directions"] else 0

        # Decision rule
        if latest_event_direction > 0 or a101 > 0.2:
            action = "BUY"
            rationale = f"Gold upward CUSUM event / Alpha101 bullish ({round(a101, 2)}), GK Vol: {round(gk_vol, 4)}"
            confidence = 0.70
        elif latest_event_direction < 0 or a101 < -0.2:
            action = "SELL"
            rationale = f"Gold downward CUSUM event / Alpha101 bearish ({round(a101, 2)}), GK Vol: {round(gk_vol, 4)}"
            confidence = 0.70
        else:
            action = "HOLD"
            rationale = "Market is in noise equilibrium; awaiting structural CUSUM trigger."
            confidence = 0.50

        current_price = float(close.iloc[-1])
        effective_lots = self.calculate_risk_parity_lot(
            account_equity=account_equity,
            current_price=current_price,
            atr=gk_vol * current_price if gk_vol > 0 else None,
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
