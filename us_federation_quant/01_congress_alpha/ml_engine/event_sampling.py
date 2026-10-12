"""
Symmetric CUSUM Filter for Event-Driven Financial Sampling.
Reference: Marcos López de Prado, Advances in Financial Machine Learning (2018), Chapter 2.5.

Replaces fixed-time arbitrary sampling (which suffers from oversampling low-volatility noise
and undersampling turbulent high-information regimes) with quality-weighted event sampling.
Triggers an observation only when cumulative price deviations exceed a dynamic volatility threshold h_t.
"""

from typing import List, Dict, Any, Optional, Union
import numpy as np
import pandas as pd


class SymmetricCUSUMFilter:
    """
    Symmetric Cumulative Sum (CUSUM) Filter for detecting structural change points.
    Tracks positive and negative running cumulative returns and samples an event
    whenever either accumulator crosses the threshold.
    """

    def __init__(
        self,
        threshold_multiplier: float = 2.0,
        default_threshold: float = 0.01
    ):
        """
        :param threshold_multiplier: Multiplier applied to dynamic volatility sigma_t (default 2.0 * sigma)
        :param default_threshold: Fallback threshold if dynamic volatility is unavailable
        """
        self.threshold_multiplier = threshold_multiplier
        self.default_threshold = default_threshold

    def filter_events(
        self,
        close_prices: Union[pd.Series, np.ndarray, List[float]],
        volatility_series: Optional[Union[pd.Series, np.ndarray, List[float]]] = None
    ) -> Dict[str, Any]:
        """
        Runs the symmetric CUSUM filter over the close price series.

        :param close_prices: Series or array of asset closing prices
        :param volatility_series: Optional series of dynamic volatilities (e.g. rolling EWM std or Garman-Klass)
        :return: Dictionary with event indices, timestamps, directions, and sampling statistics
        """
        if isinstance(close_prices, (list, np.ndarray)):
            prices = pd.Series(close_prices)
        else:
            prices = close_prices.copy()

        n = len(prices)
        if n < 3:
            return {
                "event_indices": [],
                "event_timestamps": [],
                "event_directions": [],
                "total_bars": n,
                "event_count": 0,
                "sampling_ratio": 0.0
            }

        # Calculate log returns: r_t = log(P_t / P_{t-1})
        log_returns = np.log(prices.values[1:] / prices.values[:-1])

        # Prepare threshold series h_t
        if volatility_series is not None:
            if isinstance(volatility_series, (list, np.ndarray)):
                vols = np.array(volatility_series)[1:]
            else:
                vols = volatility_series.values[1:]
            h = np.maximum(1e-4, vols * self.threshold_multiplier)
        else:
            # Estimate rolling volatility if not provided
            roll_std = pd.Series(log_returns).ewm(span=20).std().fillna(self.default_threshold).values
            h = np.maximum(1e-4, roll_std * self.threshold_multiplier)

        s_pos = 0.0
        s_neg = 0.0
        event_indices: List[int] = []
        event_timestamps: List[Any] = []
        event_directions: List[int] = []

        # prices index mapping
        index_labels = prices.index

        for i in range(len(log_returns)):
            r = log_returns[i]
            thresh = h[i] if i < len(h) else self.default_threshold

            s_pos = max(0.0, s_pos + r)
            s_neg = min(0.0, s_neg + r)

            current_idx = i + 1  # Map back to original price index

            if s_pos >= thresh:
                event_indices.append(current_idx)
                event_timestamps.append(index_labels[current_idx])
                event_directions.append(1)  # Upward structural event
                s_pos = 0.0

            elif s_neg <= -thresh:
                event_indices.append(current_idx)
                event_timestamps.append(index_labels[current_idx])
                event_directions.append(-1)  # Downward structural event
                s_neg = 0.0

        sampling_ratio = len(event_indices) / n if n > 0 else 0.0

        return {
            "event_indices": event_indices,
            "event_timestamps": event_timestamps,
            "event_directions": event_directions,
            "total_bars": n,
            "event_count": len(event_indices),
            "sampling_ratio": round(sampling_ratio, 4)
        }
