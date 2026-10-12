"""
The Federal Reserve: Emergency Liquidity Fund & Profit Sweeping Pool
Sweeps excess trading profits above base operational equity into risk-free federal reserves.
Acts as a liquidity shock absorber during market dislocations.
"""

from typing import Dict, Any


class EmergencyLiquidityFund:
    """
    Treasury & Federal Liquidity Shock Absorber.
    """

    def __init__(self, initial_reserve: float = 2_000_000.0):
        self.treasury_reserve = initial_reserve
        self.cumulative_swept_profits = 0.0

    def sweep_profits(self, current_equity: float, baseline_capital: float) -> Dict[str, float]:
        """
        Sweeps profits: If current_equity > baseline_capital, transfers excess to risk-free reserves.
        """
        excess = current_equity - baseline_capital
        if excess > 0:
            self.treasury_reserve += excess
            self.cumulative_swept_profits += excess
            swept = excess
            retained = baseline_capital
        else:
            swept = 0.0
            retained = current_equity

        return {
            "swept_amount": float(round(swept, 2)),
            "retained_equity": float(round(retained, 2)),
            "treasury_reserve": float(round(self.treasury_reserve, 2)),
            "cumulative_swept_profits": float(round(self.cumulative_swept_profits, 2))
        }
