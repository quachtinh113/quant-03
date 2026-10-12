"""
VWAP (Volume-Weighted Average Price) Intraday Liquidity Slicer.
Models the empirical U-shaped (smile) intraday volume profile:
High liquidity at session Open and Close, subdued volume during midday consolidation.
Slices parent orders proportionally to expected market liquidity to minimize slippage.
"""

from typing import List, Dict, Any, Optional


class VWAPProfileSlicer:
    """
    Intraday Volume-Weighted Execution Profiler.
    Generates non-linear execution slices matching empirical market volume distributions.
    """

    def __init__(self, curvature: float = 2.0, base_liquidity_floor: float = 0.5):
        """
        :param curvature: Curvature parameter governing the depth of the midday volume trough.
        :param base_liquidity_floor: Minimum liquidity fraction at the midday trough relative to peaks.
        """
        self.curvature = curvature
        self.base_liquidity_floor = base_liquidity_floor

    def get_normalized_volume_curve(self, n_slices: int = 5) -> List[float]:
        """
        Computes the discrete U-curve normalized weights summing to 1.0.
        f(u) = base_floor + curvature * (u - 0.5)^2 for u in [0, 1]
        """
        if n_slices <= 0:
            return []
        if n_slices == 1:
            return [1.0]

        raw_weights: List[float] = []
        for i in range(n_slices):
            # Centered interval u in [0, 1]
            u = (i + 0.5) / n_slices
            weight = self.base_liquidity_floor + self.curvature * ((u - 0.5) ** 2)
            raw_weights.append(weight)

        total_weight = sum(raw_weights)
        return [w / total_weight for w in raw_weights]

    def slice_order(
        self,
        total_lots: float,
        n_slices: int = 5,
        custom_weights: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Slices total order volume into VWAP child orders matching the volume profile.

        :param total_lots: Total volume in lots to be routed
        :param n_slices: Number of execution buckets
        :param custom_weights: Optional empirical historical volume bucket weights
        :return: List of slice details with slice lot, volume fraction, and step index
        """
        if n_slices < 1:
            raise ValueError("Number of slices must be at least 1.")
        if total_lots <= 0:
            return []

        if custom_weights is not None:
            if len(custom_weights) != n_slices:
                raise ValueError("custom_weights length must match n_slices.")
            s = sum(custom_weights)
            weights = [w / s for w in custom_weights]
        else:
            weights = self.get_normalized_volume_curve(n_slices)

        # Allocate lots per bucket
        raw_allocations = [total_lots * w for w in weights]
        rounded_allocations = [round(a, 2) for a in raw_allocations]

        # Balance rounding drift to guarantee sum(rounded_allocations) == total_lots
        diff = round(total_lots - sum(rounded_allocations), 2)
        if abs(diff) > 1e-4:
            # Allocate difference to the bucket with the highest weight (peak volume)
            max_idx = weights.index(max(weights))
            rounded_allocations[max_idx] = round(rounded_allocations[max_idx] + diff, 2)

        slices: List[Dict[str, Any]] = []
        for i in range(n_slices):
            slices.append({
                "step": i + 1,
                "total_steps": n_slices,
                "weight": round(weights[i], 4),
                "slice_lots": rounded_allocations[i],
                "expected_volume_ratio": round(weights[i], 4)
            })

        return slices
