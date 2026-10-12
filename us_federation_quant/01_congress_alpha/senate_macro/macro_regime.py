"""
The Senate (Thượng viện — 100 Seats)
Macro Regime & Long-Term Trend Authority.
Evaluates Andrew Lo & Craig MacKinlay Variance Ratio and Macro Trend Filters.
Ensures micro-fluctuations do not counter structural macro tides.
"""

from typing import Dict, Any
import numpy as np
import pandas as pd


def lo_mackinlay_variance_ratio(prices: np.ndarray, q: int = 5) -> float:
    """
    Computes Lo-MacKinlay Variance Ratio VR(q).
    VR(q) > 1.0 -> Trending / Momentum Regime
    VR(q) < 1.0 -> Mean-Reverting Regime
    VR(q) == 1.0 -> Random Walk / Efficient Market
    """
    if len(prices) < q * 4:
        return 1.0

    returns_1 = np.diff(prices) / prices[:-1]
    returns_q = (prices[q:] - prices[:-q]) / prices[:-q]

    var_1 = np.var(returns_1, ddof=1)
    var_q = np.var(returns_q, ddof=1)

    if var_1 <= 1e-12:
        return 1.0

    vr = var_q / (q * var_1)
    return float(vr)


class SenateMacro:
    """
    The Senate (100 Seats).
    2 Senators per state evaluating macro regime and structural price momentum.
    """

    TOTAL_SEATS: int = 100

    @classmethod
    def vote_on_regime(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Polls the 100 Senators on whether the proposed trade aligns with macro structural reality.
        """
        if len(df) < 20:
            return {"passed": False, "yes_votes": 50, "no_votes": 50, "regime": "UNDEFINED"}

        close = df["close"].values
        vr = lo_mackinlay_variance_ratio(close, q=5)
        
        # Long-term SMA vs current price
        sma_50 = pd.Series(close).rolling(50, min_periods=10).mean().iloc[-1]
        current_price = close[-1]
        
        trend_direction = "BUY" if current_price >= sma_50 else "SELL"
        
        # Regime determination
        if vr > 1.05:
            regime = "MOMENTUM_TREND"
            regime_strength = min(1.0, (vr - 1.0) * 2.0)
        elif vr < 0.95:
            regime = "MEAN_REVERSION"
            regime_strength = min(1.0, (1.0 - vr) * 2.0)
        else:
            regime = "RANDOM_WALK"
            regime_strength = 0.0

        # Calculate Senate vote
        # Trending regime with price above SMA50 gives strong BUY consensus
        if current_price >= sma_50 and vr >= 1.0:
            yes_votes = int(round(50 + 45 * regime_strength))
        elif current_price < sma_50 and vr >= 1.0:
            yes_votes = int(round(50 - 45 * regime_strength))
        else:
            yes_votes = 52 # Modest majority

        no_votes = cls.TOTAL_SEATS - yes_votes
        passed = yes_votes >= 51 # Simple majority in 100 seats

        return {
            "passed": passed,
            "yes_votes": yes_votes,
            "no_votes": no_votes,
            "macro_trend": trend_direction,
            "variance_ratio": round(vr, 4),
            "regime": regime
        }
