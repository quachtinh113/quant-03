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
    carver_forecast: float = 0.0          # Continuous forecast in [-20.0, +20.0]
    raw_lots: float = 0.0                 # Unbuffered target lots
    buffered_lots: float = 0.0            # Trade buffered lots
    is_buffered: bool = False             # Whether buffering prevented an unnecessary trade
    cash_vol_budget: float = 0.0          # Daily cash volatility allocated by the Fed


class BaseStatePod(StatePod):
    """
    Autonomous Strategy Pod with localized risk governance, Carver continuous
    forecasting, and localized drawdown management.
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

    # ----------------------------------------------------------------------------------
    # ROBERT CARVER CONTINUOUS FORECASTING ENGINE (pysystemtrade)
    # ----------------------------------------------------------------------------------
    def calculate_continuous_forecast(
        self,
        market_df: pd.DataFrame,
        fast_period: int = 8,
        slow_period: int = 32,
    ) -> float:
        """
        Robert Carver Continuous Forecast Engine (pysystemtrade).
        Maps market indicators to a standardized [-20.0, +20.0] continuous scalar.
        - +10: Standard buy
        - +20: Maximum conviction buy (capped)
        - -10: Standard short
        - -20: Maximum conviction short (capped)
        - 0: Neutral equilibrium
        """
        if len(market_df) < max(20, slow_period):
            return 0.0

        close = market_df["close"].values
        current_price = float(close[-1])

        # Dual mode: Mean-Reversion or EWMAC Trend based on pod strategy style
        if "REVERSION" in self.strategy_style.upper() or "SCALP" in self.strategy_style.upper():
            # Mean reversion forecast (inverts standardized z-score)
            ma = float(np.mean(close[-20:]))
            std = float(np.std(close[-20:]))
            if std <= 1e-8:
                return 0.0
            z_score = (current_price - ma) / std
            raw_forecast = -z_score * 10.0
        else:
            # EWMAC (Exponentially Weighted Moving Average Crossover) trend forecast
            ema_fast = pd.Series(close).ewm(span=fast_period).mean().iloc[-1]
            ema_slow = pd.Series(close).ewm(span=slow_period).mean().iloc[-1]
            raw_diff = float(ema_fast - ema_slow)

            # Divide by rolling price volatility to obtain risk-normalized forecast
            returns = np.diff(close) / np.maximum(1e-8, close[:-1])
            ann_vol = float(np.std(returns[-30:]) * np.sqrt(256) * current_price) if len(returns) >= 30 else current_price * 0.01
            scalar = 10.0 / (ann_vol * 0.05) if ann_vol > 0 else 1.0
            raw_forecast = raw_diff * scalar

        # Carver Forecast Capping: Strictly bound between -20.0 and +20.0
        capped_forecast = float(np.clip(raw_forecast, -20.0, 20.0))
        return round(capped_forecast, 2)

    def calculate_carver_target_position(
        self,
        cash_vol_target: float,
        forecast: float,
        current_position_lot: float = 0.0,
        atr_price: Optional[float] = None,
        contract_size: Optional[float] = None,
        buffer_fraction: float = 0.10,
        min_lot: float = 0.01,
        max_lot: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Robert Carver Block Value & Volatility Target Position Sizing:
        1. Dollar Risk per Contract = ATR * ContractSize
        2. Raw Target Lots = (Cash Vol Target * (|Forecast| / 10.0)) / Dollar Risk per Contract
        3. Carver Trade Buffering (+/- 10%) against current_position_lot to eliminate churn.
        """
        clean_asset = self.primary_asset.upper().replace("M", "")
        if contract_size is None:
            if "XAU" in clean_asset or "GOLD" in clean_asset:
                contract_size = 100.0
            elif "US30" in clean_asset or "US500" in clean_asset or "USTEC" in clean_asset or "BTC" in clean_asset:
                contract_size = 1.0
            else:
                contract_size = 100_000.0

        effective_atr = atr_price if (atr_price and atr_price > 0) else 10.0
        dollar_risk_per_contract = effective_atr * contract_size
        if dollar_risk_per_contract <= 0:
            dollar_risk_per_contract = 100.0

        forecast_scalar = abs(forecast) / 10.0
        raw_target_lots = (cash_vol_target * forecast_scalar) / dollar_risk_per_contract
        raw_target_lots = float(np.clip(raw_target_lots, 0.0, max_lot))

        # Apply state pod capital multiplier (Drawdown Ladder)
        raw_target_lots = raw_target_lots * self.capital_multiplier

        # Position Buffering (+/- 10%)
        is_buffered = False
        buffered_lots = raw_target_lots
        if current_position_lot > 0.0:
            diff = abs(raw_target_lots - current_position_lot)
            if diff <= buffer_fraction * current_position_lot:
                buffered_lots = current_position_lot
                is_buffered = True

        final_lots = round(buffered_lots, 2)
        if final_lots > 0 and final_lots < min_lot:
            final_lots = min_lot

        return {
            "raw_lots": round(raw_target_lots, 2),
            "buffered_lots": final_lots,
            "is_buffered": is_buffered,
            "dollar_risk_per_contract": round(dollar_risk_per_contract, 2),
            "forecast_scalar": round(forecast_scalar, 2),
        }

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

        target_risk_usd = max(1.0, account_equity * risk_fraction)
        effective_atr = atr if (atr and atr > 0) else (current_price * 0.005)
        dollar_risk_per_lot = effective_atr * contract_size * 1.5

        if dollar_risk_per_lot > 0:
            raw_lot = target_risk_usd / dollar_risk_per_lot
        else:
            raw_lot = 0.01

        effective_lot = raw_lot * self.capital_multiplier
        final_lot = max(0.01, min(round(effective_lot, 2), max_lot))
        return final_lot

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        account_equity: float = 10000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposal with Carver Continuous Forecast [-20, +20]
        and dynamic volatility-targeted sizing with position buffering.
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
        std20 = float(np.std(close[-20:]))

        # 1. Compute Carver Continuous Forecast in [-20.0, +20.0]
        forecast = self.calculate_continuous_forecast(market_df)

        # 2. Determine Action & Conviction
        if forecast >= 2.0:
            action = "BUY"
            confidence = min(0.95, 0.50 + (forecast / 40.0))
            rationale = f"Carver Bullish Continuous Forecast: {forecast:+.2f} / +20.0"
        elif forecast <= -2.0:
            action = "SELL"
            confidence = min(0.95, 0.50 + (abs(forecast) / 40.0))
            rationale = f"Carver Bearish Continuous Forecast: {forecast:+.2f} / -20.0"
        else:
            action = "HOLD"
            confidence = 0.50
            rationale = f"Carver Neutral Forecast: {forecast:+.2f} (Within equilibrium [-2.0, +2.0])"

        # 3. Position Sizing: Carver Vol Target if budget available, else Risk Parity
        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=std20 if std20 > 0 else current_price * 0.005,
            )
            raw_lots = carver_sizing["raw_lots"]
            target_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=std20 if std20 > 0 else current_price * 0.005,
            )
            target_lots = raw_lots
            is_buffered = False
        else:
            raw_lots = 0.0
            target_lots = 0.0
            is_buffered = False

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=target_lots,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD",
            carver_forecast=forecast,
            raw_lots=raw_lots,
            buffered_lots=target_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )

