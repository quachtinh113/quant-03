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
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on CUSUM structural events, Garman-Klass volatility,
        and Robert Carver continuous forecasting [-20, +20].
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

        # Continuous Carver forecast in [-20.0, +20.0]
        raw_forecast = (a101 * 15.0) + (latest_event_direction * 10.0)
        forecast = float(np.clip(raw_forecast, -20.0, 20.0))

        # Decision rule
        if forecast >= 2.0:
            action = "BUY"
            rationale = f"Gold upward CUSUM / Alpha101 bullish: Forecast {forecast:+.2f}, GK Vol: {round(gk_vol, 4)}"
            confidence = min(0.95, 0.50 + (forecast / 40.0))
        elif forecast <= -2.0:
            action = "SELL"
            rationale = f"Gold downward CUSUM / Alpha101 bearish: Forecast {forecast:+.2f}, GK Vol: {round(gk_vol, 4)}"
            confidence = min(0.95, 0.50 + (abs(forecast) / 40.0))
        else:
            action = "HOLD"
            rationale = f"Gold in noise equilibrium: Forecast {forecast:+.2f} (Within [-2.0, +2.0])"
            confidence = 0.50

        current_price = float(close.iloc[-1])
        atr_price = gk_vol * current_price if gk_vol > 0 else current_price * 0.005

        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            lot_cap = 0.05 if account_equity <= 25000.0 else (0.20 if account_equity <= 100000.0 else 5.0)
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=atr_price,
                contract_size=100.0,
                max_lot=lot_cap,
            )
            raw_lots = carver_sizing["raw_lots"]
            effective_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=atr_price,
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
