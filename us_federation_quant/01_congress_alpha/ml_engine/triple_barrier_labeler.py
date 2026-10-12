"""
Triple Barrier Labeling Method for Financial Machine Learning & Meta-Labeling.
Reference: Marcos López de Prado, Advances in Financial Machine Learning (2018), Chapter 3.

Constructs 3 dynamic, path-dependent barriers for each trade event:
1. Upper Barrier: Dynamic Take-Profit (pt * sigma_t)
2. Lower Barrier: Dynamic Stop-Loss (sl * sigma_t)
3. Vertical Barrier: Maximum Holding Time Expiration (t + Delta_t)

Generates binary Meta-Labels:
y = 1: Primary trade reached Profit Target before Stop-Loss (True Positive / Success)
y = 0: Primary trade hit Stop-Loss or expired with non-positive return (False Positive / Failure)
"""

from typing import List, Dict, Any, Optional, Union
import numpy as np
import pandas as pd


class TripleBarrierLabeler:
    """
    Computes path-dependent trade outcomes and binary Meta-Labels.
    """

    def __init__(
        self,
        pt_multiplier: float = 2.0,       # Take-Profit multiplier (in units of dynamic volatility)
        sl_multiplier: float = 1.0,       # Stop-Loss multiplier (in units of dynamic volatility)
        max_holding_period: int = 20,     # Vertical barrier (max bars before timeout)
        min_return_threshold: float = 0.0 # Min realized return for timeout to be considered win
    ):
        self.pt_multiplier = pt_multiplier
        self.sl_multiplier = sl_multiplier
        self.max_holding_period = max_holding_period
        self.min_return_threshold = min_return_threshold

    def apply_barriers(
        self,
        df: pd.DataFrame,
        event_indices: List[int],
        primary_signals: Optional[List[int]] = None,
        volatility_series: Optional[Union[pd.Series, np.ndarray, List[float]]] = None
    ) -> pd.DataFrame:
        """
        Applies triple barriers to each event and labels the path outcome.

        :param df: DataFrame containing at least 'close' (and optionally 'high', 'low') columns
        :param event_indices: List of integer bar indices where trading events/signals occur
        :param primary_signals: Trade direction (+1 for BUY, -1 for SELL). Defaults to +1 (BUY) for all events.
        :param volatility_series: Dynamic volatility sigma_t (e.g. Garman-Klass or EWM return std)
        :return: DataFrame of labeled events with start/end indices, exit reason, return, and binary label
        """
        if len(event_indices) == 0:
            return pd.DataFrame(columns=[
                "entry_idx", "exit_idx", "holding_period", "entry_price", "exit_price",
                "realized_return", "exit_reason", "side", "label"
            ])

        close = df["close"].values
        high = df["high"].values if "high" in df.columns else close
        low = df["low"].values if "low" in df.columns else close
        n = len(close)

        # Volatility setup
        if volatility_series is not None:
            if isinstance(volatility_series, (list, np.ndarray)):
                vols = np.array(volatility_series)
            else:
                vols = volatility_series.values
        else:
            # Fallback 20-bar rolling standard deviation of percentage returns
            pct = pd.Series(close).pct_change().fillna(0.01)
            vols = pct.rolling(20, min_periods=5).std().fillna(0.01).values

        if primary_signals is None:
            signals = [1] * len(event_indices)
        else:
            signals = primary_signals

        records: List[Dict[str, Any]] = []

        for idx, side in zip(event_indices, signals):
            if idx >= n - 1:
                continue

            entry_price = close[idx]
            sigma = max(1e-4, vols[idx])

            # Dynamic barrier levels relative to entry price
            if side == 1:  # BUY trade
                upper_tp = entry_price * (1.0 + self.pt_multiplier * sigma)
                lower_sl = entry_price * (1.0 - self.sl_multiplier * sigma)
            else:          # SELL trade
                upper_tp = entry_price * (1.0 - self.pt_multiplier * sigma)
                lower_sl = entry_price * (1.0 + self.sl_multiplier * sigma)

            vertical_idx = min(n - 1, idx + self.max_holding_period)

            exit_idx = vertical_idx
            exit_reason = "VERTICAL_TIMEOUT"
            exit_price = close[vertical_idx]

            # Path simulation between entry and vertical barrier
            for step in range(idx + 1, vertical_idx + 1):
                h_step = high[step]
                l_step = low[step]

                if side == 1:
                    # BUY trade: profit if high >= upper_tp, stop if low <= lower_sl
                    hit_tp = h_step >= upper_tp
                    hit_sl = l_step <= lower_sl

                    if hit_tp and not hit_sl:
                        exit_idx = step
                        exit_price = upper_tp
                        exit_reason = "TAKE_PROFIT"
                        break
                    elif hit_sl and not hit_tp:
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break
                    elif hit_tp and hit_sl:
                        # Simultaneous touch: conservative resolution is STOP_LOSS
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break

                else:
                    # SELL trade: profit if low <= upper_tp (downward), stop if high >= lower_sl (upward)
                    hit_tp = l_step <= upper_tp
                    hit_sl = h_step >= lower_sl

                    if hit_tp and not hit_sl:
                        exit_idx = step
                        exit_price = upper_tp
                        exit_reason = "TAKE_PROFIT"
                        break
                    elif hit_sl and not hit_tp:
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break
                    elif hit_tp and hit_sl:
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break

            # Calculate realized return based on trade side
            if side == 1:
                realized_return = (exit_price - entry_price) / entry_price
            else:
                realized_return = (entry_price - exit_price) / entry_price

            # Binary Meta-Label: 1 if success (hit TP or positive return upon expiration), 0 otherwise
            if exit_reason == "TAKE_PROFIT":
                label = 1
            elif exit_reason == "STOP_LOSS":
                label = 0
            else:
                label = 1 if realized_return > self.min_return_threshold else 0

            records.append({
                "entry_idx": idx,
                "exit_idx": exit_idx,
                "holding_period": exit_idx - idx,
                "entry_price": round(float(entry_price), 4),
                "exit_price": round(float(exit_price), 4),
                "realized_return": round(float(realized_return), 5),
                "exit_reason": exit_reason,
                "side": side,
                "label": int(label)
            })

        return pd.DataFrame(records)
