"""
Avellaneda-Stoikov Market Microstructure Execution Engine
High-frequency inventory-based spread model (High-Frequency Trading in a Limit Order Book, 2008).
Optimizes bid/ask quote placement relative to current inventory and volatility.
"""

import math
from typing import Dict, Any


class AvellanedaStoikovEngine:
    """
    Computes optimal reservation prices and spread placement.
    r(s, q, t) = s - q * gamma * sigma^2 * (T - t) + theta * OFI * sigma
    Incorporates Order Flow Imbalance (OFI) and adverse selection spread widening.
    """

    def __init__(
        self,
        gamma: float = 0.1,           # Risk aversion parameter
        kappa: float = 1.5,           # Order book liquidity density parameter
        time_horizon: float = 1.0,    # Time horizon T
        ofi_sensitivity: float = 0.25 # Adverse selection sensitivity to OFI
    ):
        self.gamma = gamma
        self.kappa = kappa
        self.time_horizon = time_horizon
        self.ofi_sensitivity = ofi_sensitivity

    def calculate_quotes(
        self,
        mid_price: float,
        inventory_q: float,
        volatility_sigma: float,
        time_remaining_t: float = 1.0,
        order_flow_imbalance: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculates reservation price and optimal bid/ask offsets.
        
        :param mid_price: Current market mid-price
        :param inventory_q: Current inventory position (positive = long, negative = short)
        :param volatility_sigma: Volatility (relative or dollar vol)
        :param time_remaining_t: Remaining time horizon fraction (0 < t <= 1)
        :param order_flow_imbalance: Normalized Order Flow Imbalance in [-1.0, 1.0]
        """
        # Convert relative volatility to dollar volatility if sigma < 1.0
        dollar_vol = (volatility_sigma * mid_price) if volatility_sigma < 1.0 else volatility_sigma

        # Inventory risk penalty
        inventory_penalty = (inventory_q * self.gamma * (dollar_vol ** 2) * time_remaining_t) / mid_price
        
        # Order Flow Imbalance (OFI) directional alpha drift adjustment
        # Positive OFI (buyer pressure) shifts reservation price upwards
        # Negative OFI (seller pressure) shifts reservation price downwards
        ofi_drift = self.ofi_sensitivity * order_flow_imbalance * dollar_vol * time_remaining_t
        
        reservation_price = mid_price - inventory_penalty + ofi_drift

        # Base half-spread term
        spread_term = ((self.gamma * (dollar_vol ** 2) * time_remaining_t) / mid_price) + (
            (2.0 / self.gamma) * math.log(1.0 + (self.gamma / self.kappa))
        )
        base_half_spread = max(0.01, spread_term / 2.0)

        # Adverse selection widening: when |OFI| is elevated, informed trading risk rises
        adverse_selection_multiplier = 1.0 + 0.5 * abs(order_flow_imbalance)
        half_spread = base_half_spread * adverse_selection_multiplier

        bid_price = round(reservation_price - half_spread, 4)
        ask_price = round(reservation_price + half_spread, 4)
        skew_offset = round(reservation_price - mid_price, 4)

        return {
            "mid_price": mid_price,
            "reservation_price": round(reservation_price, 4),
            "optimal_bid": bid_price,
            "optimal_ask": ask_price,
            "spread": round(ask_price - bid_price, 4),
            "skew_offset": skew_offset,
            "order_flow_imbalance": order_flow_imbalance
        }

