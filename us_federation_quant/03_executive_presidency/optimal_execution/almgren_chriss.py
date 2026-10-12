"""
Almgren-Chriss (2000) Optimal Execution Trajectory Engine.
Reference: Almgren, R., & Chriss, N. (2000). Optimal execution of portfolio transactions.
Journal of Risk, 3, 5-40.

Calculates the optimal trade schedule balancing temporary market impact against inventory risk (volatility exposure).
Minimizes Expected Cost + lambda * Variance of Cost.
"""

import math
from typing import List, Dict, Any


class AlmgrenChrissExecutor:
    """
    Computes discrete optimal trading trajectories under the Almgren-Chriss framework.
    """

    def __init__(
        self,
        risk_aversion_lambda: float = 1e-4,  # Risk aversion parameter lambda
        temp_impact_eta: float = 2.5e-4,     # Temporary market impact coefficient eta
        perm_impact_gamma: float = 1e-5      # Permanent market impact coefficient gamma
    ):
        self.risk_aversion_lambda = max(1e-8, risk_aversion_lambda)
        self.temp_impact_eta = max(1e-8, temp_impact_eta)
        self.perm_impact_gamma = max(1e-8, perm_impact_gamma)

    def calculate_trajectory(
        self,
        total_lots: float,
        volatility_sigma: float = 0.015,
        time_horizon: float = 1.0,
        n_slices: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Computes the optimal inventory holdings and trade slice sizes across N intervals.

        :param total_lots: Initial total order size X_0 to execute/liquidate
        :param volatility_sigma: Market volatility (standard deviation of price changes)
        :param time_horizon: Total time duration T (e.g. 1.0 day or session)
        :param n_slices: Number of execution steps N (intervals)
        :return: List of step dictionaries with slice size, remaining inventory, and timing
        """
        if n_slices < 1:
            raise ValueError("Number of slices must be at least 1.")
        if total_lots <= 0:
            return []

        tau = time_horizon / n_slices

        # Characteristic decay rate kappa:
        # In Almgren-Chriss (2000), kappa = sqrt(lambda * sigma^2 / eta)
        variance_penalty = (self.risk_aversion_lambda * (volatility_sigma ** 2)) / self.temp_impact_eta
        if variance_penalty <= 1e-12:
            kappa = 0.0
        else:
            kappa = math.sqrt(variance_penalty)


        # Compute inventory holdings x_j at time t_j = j * tau for j = 0, ..., N
        # x_0 = total_lots, x_N = 0.0
        x = [0.0] * (n_slices + 1)
        x[0] = total_lots

        if kappa * time_horizon < 1e-5:
            # Risk-neutral linear trajectory (TWAP limit)
            for j in range(1, n_slices + 1):
                t_j = j * tau
                x[j] = total_lots * (1.0 - t_j / time_horizon)
        else:
            sinh_kappa_T = math.sinh(kappa * time_horizon)
            for j in range(1, n_slices + 1):
                t_j = j * tau
                x[j] = total_lots * (math.sinh(kappa * (time_horizon - t_j)) / sinh_kappa_T)
        
        # Ensure final inventory is exactly 0
        x[n_slices] = 0.0

        # Calculate trade slice sizes n_j = x_{j-1} - x_j
        raw_slices = [x[j - 1] - x[j] for j in range(1, n_slices + 1)]

        # Round to 2 decimal places (standard 0.01 lot step)
        rounded_slices = [round(s, 2) for s in raw_slices]
        diff = round(total_lots - sum(rounded_slices), 2)

        # Distribute any fractional rounding discrepancy to largest slice
        if abs(diff) > 1e-4:
            max_idx = rounded_slices.index(max(rounded_slices))
            rounded_slices[max_idx] = round(rounded_slices[max_idx] + diff, 2)

        schedule: List[Dict[str, Any]] = []
        accumulated = 0.0
        for j in range(1, n_slices + 1):
            slice_lot = rounded_slices[j - 1]
            accumulated += slice_lot
            rem_inv = round(max(0.0, total_lots - accumulated), 2)
            schedule.append({
                "step": j,
                "total_steps": n_slices,
                "time_fraction": round(j * tau / time_horizon, 4),
                "slice_lots": slice_lot,
                "remaining_lots": rem_inv,
                "raw_optimal_lots": round(raw_slices[j - 1], 4)
            })

        return schedule
