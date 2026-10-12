"""
State 05: NowTrading Multi-Timeframe (MTF) RSI Pod.
Resurrected and sanitized version of the legacy NOWTRADING 2.1 bot.
- DCA completely removed.
- Enforced hard Stop Loss through Central Risk Desk.
- Logic: MTF RSI (H4/H1 trend + M15 Pullback Exhaustion).
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
import pandas_ta as ta

from ..base_pod import BaseStatePod, StateTradeProposal

class NowTradingMtfPod(BaseStatePod):
    """
    Sovereign State 05: NowTrading MTF Pullback Strategy.
    """

    def __init__(self, allocated_capital: float = 250_000.0, primary_asset: str = "XAUUSDm"):
        super().__init__(
            state_id="STATE_05",
            state_name="State of NowTrading MTF",
            primary_asset=primary_asset,
            strategy_style="MTF RSI Trend Pullback",
            timeframe="M15",
            allocated_capital=allocated_capital
        )
        # Core thresholds from original signal_engine.py
        self.rsi_period = 14
        self.rsi_buy = 55.0
        self.rsi_sell = 45.0
        self.rsi_pullback = 50.0

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        account_equity: float = 1000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on MTF RSI and Pullback Exhaustion,
        with Carver continuous forecasting, cash volatility budgeting, and position buffering.
        NOTE: This expects market_df to be M15 data, but in a real MTF setup, 
        we simulate H1/H4 RSI by using longer RSI periods or downsampled data.
        For this pod, we approximate H1 as M15 * 4, H4 as M15 * 16.
        """
        if not self.is_active or self.is_quarantined:
            return self._hold_proposal("State is quarantined or inactive.", "STATE_QUARANTINED")

        if len(market_df) < self.rsi_period * 16 + 2:
            return self._hold_proposal("Insufficient bar history for H4 approximation.", "INSUFFICIENT_DATA")

        close = market_df["close"]

        # Approximate MTF RSI using extended periods
        rsi_m15 = ta.rsi(close, length=self.rsi_period)
        rsi_h1 = ta.rsi(close, length=self.rsi_period * 4)
        rsi_h4 = ta.rsi(close, length=self.rsi_period * 16)
        
        if rsi_m15 is None or rsi_h1 is None or rsi_h4 is None:
             return self._hold_proposal("RSI calculation failed.", "RSI_FAILED")

        val_m15 = rsi_m15.iloc[-1]
        val_h1 = rsi_h1.iloc[-1]
        val_h4 = rsi_h4.iloc[-1]
        
        prev_m15 = rsi_m15.iloc[-2]
        
        # Pullback exhaustion logic from legacy engine
        m15_rsi_rising = val_m15 > prev_m15
        m15_rsi_falling = val_m15 < prev_m15
        
        m15_close_rising = close.iloc[-1] > close.iloc[-2]
        m15_close_falling = close.iloc[-1] < close.iloc[-2]
        
        # Lookback for local highs/lows
        lb = 3
        local_lows = market_df["low"].iloc[-1 - lb : -1]
        local_highs = market_df["high"].iloc[-1 - lb : -1]
        
        m15_fresh_local_low = market_df["low"].iloc[-1] < local_lows.min()
        m15_fresh_local_high = market_df["high"].iloc[-1] > local_highs.max()

        action = "HOLD"
        rationale = "No signal"
        confidence = 0.50
        forecast = 0.0

        # BUY LOGIC
        if val_h4 > self.rsi_buy and val_h1 > self.rsi_buy:
            if val_m15 > self.rsi_pullback and m15_rsi_rising and m15_close_rising and not m15_fresh_local_low:
                action = "BUY"
                raw_fc = 5.0 + (val_h4 - self.rsi_buy) * 0.5 + (val_m15 - self.rsi_pullback) * 0.5
                forecast = float(np.clip(raw_fc, -20.0, 20.0))
                rationale = f"BUY: RSI H4={val_h4:.1f} H1={val_h1:.1f} M15={val_m15:.1f} (Pullback Exhausted)"
                confidence = 0.75

        # SELL LOGIC
        elif val_h4 < self.rsi_sell and val_h1 < self.rsi_sell:
            if val_m15 < self.rsi_pullback and m15_rsi_falling and m15_close_falling and not m15_fresh_local_high:
                action = "SELL"
                raw_fc = -5.0 - (self.rsi_sell - val_h4) * 0.5 - (self.rsi_pullback - val_m15) * 0.5
                forecast = float(np.clip(raw_fc, -20.0, 20.0))
                rationale = f"SELL: RSI H4={val_h4:.1f} H1={val_h1:.1f} M15={val_m15:.1f} (Pullback Exhausted)"
                confidence = 0.75

        if action == "HOLD":
            return self._hold_proposal(rationale, "NO_TRIGGER")

        current_price = float(close.iloc[-1])
        atr_series = ta.atr(market_df["high"], market_df["low"], close, length=14)
        atr = float(atr_series.iloc[-1]) if atr_series is not None and not np.isnan(atr_series.iloc[-1]) else current_price * 0.005
        
        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=atr,
                contract_size=100.0,
            )
            raw_lots = carver_sizing["raw_lots"]
            effective_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=atr,
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
            is_valid=True,
            carver_forecast=round(forecast, 2),
            raw_lots=raw_lots,
            buffered_lots=effective_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )

    def _hold_proposal(self, rationale: str, rejection_reason: str) -> StateTradeProposal:
        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action="HOLD",
            target_lots=0.0,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=0.0,
            is_valid=False,
            rejection_reason=rejection_reason
        )
