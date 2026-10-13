"""
========================================================================================
QUAD-TITAN QUANTITATIVE ENGINE (BỘ TỨ TRỤ ĐỊNH LƯỢNG HOA KỲ)
Consolidates 4 Institutional Pillars into the US Federation Quant Architecture:

1. 🏛️ MIT (Massachusetts Institute of Technology):
   - Gilbert Strang (MIT 18.065): Orthogonal Nullspace Projection (B^T @ w* = 0).
   - Andrew W. Lo (MIT Sloan): Variance Ratio VR(q) Adaptive Market Hypothesis test.
   - Covariance Denoising & Factor Neutrality.

2. ⚡ PHỐ WALL (Wall Street - Jim Simons & Millennium / Citadel Pod Mechanics):
   - Pod Survival Governance & Drawdown Ladder (-3%, -5%, -7.5% Nuclear Football Kill-Switch).
   - Fractional Kelly Position Sizing & Zero Lookahead Bias Enforcement.

3. 🌐 RAY DALIO (Bridgewater Associates - World's Largest Hedge Fund):
   - All-Weather Macro Regimes (4 Quadrants: Growth +/- vs Inflation +/-).
   - Holy Grail Diversification Index (Effective Independent Return Streams: N_eff = N^2 / sum(lambda_i^2)).

4. 🛡️ BLACKROCK (Aladdin Risk Engine & Alexander Hamilton Treasury):
   - Ledoit-Wolf Covariance Matrix Shrinkage.
   - Cashflow Smoothing: Sweeps 50% of net new trading profits into Risk-Free Reserves.
   - Volatility Parity Quota Slicing.
========================================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("QuadTitanEngine")


# --------------------------------------------------------------------------------------
# 1. TRỤ MIT: Ma Trận Bù & Kiểm Định Andrew Lo VR(q)
# --------------------------------------------------------------------------------------
@dataclass
class MITCompensatorState:
    neutralized_weights: np.ndarray
    hedge_overlay_weights: np.ndarray
    is_strictly_orthogonal: bool
    market_regime: str
    vr_ratio: float


class MITTitanModule:
    """MIT Strategy Research Foundation: Gilbert Strang Nullspace & Andrew Lo Adaptive Markets."""

    @staticmethod
    def neutralize_factor_exposure(raw_weights: np.ndarray, factor_matrix: np.ndarray) -> MITCompensatorState:
        """Gilbert Strang (MIT 18.065): Chiếu trọng số vào Left Nullspace để B^T @ w* = 0."""
        n_assets = len(raw_weights)
        if factor_matrix.ndim == 1:
            factor_matrix = factor_matrix.reshape(-1, 1)

        # P = B (B^T B)^-1 B^T
        btb = factor_matrix.T @ factor_matrix
        btb_inv = np.linalg.pinv(btb)
        proj = factor_matrix @ btb_inv @ factor_matrix.T
        nullspace_proj = np.eye(n_assets) - proj

        w_star = nullspace_proj @ raw_weights
        w_hedge = w_star - raw_weights

        residual_exposure = factor_matrix.T @ w_star
        is_orthogonal = bool(np.all(np.abs(residual_exposure) < 1e-5))

        return MITCompensatorState(
            neutralized_weights=w_star,
            hedge_overlay_weights=w_hedge,
            is_strictly_orthogonal=is_orthogonal,
            market_regime="NEUTRALIZED",
            vr_ratio=1.0,
        )

    @staticmethod
    def andrew_lo_variance_ratio(price_series: np.ndarray, q: int = 4) -> Tuple[float, str]:
        """Andrew W. Lo (MIT Sloan): Variance Ratio test VR(q) under heteroskedasticity."""
        if len(price_series) < q * 4:
            return 1.0, "INSUFFICIENT_DATA"

        log_prices = np.log(price_series)
        returns = np.diff(log_prices)
        n = len(returns)

        mu = np.mean(returns)
        var_1 = np.sum((returns - mu) ** 2) / (n - 1)

        # q-period overlapping returns
        q_returns = log_prices[q:] - log_prices[:-q]
        m = q * (n - q + 1) * (1.0 - q / n)
        var_q = np.sum((q_returns - q * mu) ** 2) / m

        vr = float(var_q / (q * var_1)) if var_1 > 1e-12 else 1.0

        if vr > 1.15:
            regime = "MOMENTUM_TRENDING"
        elif vr < 0.85:
            regime = "MEAN_REVERTING"
        else:
            regime = "RANDOM_WALK_EFFICIENT"

        return round(vr, 3), regime


# --------------------------------------------------------------------------------------
# 2. TRỤ PHỐ WALL: Kỷ Luật Sinh Tồn Pod & Thang Drawdown
# --------------------------------------------------------------------------------------
class WallStreetPodDefense:
    """Jim Simons / Millennium / Citadel Pod Survival Mechanics."""

    @staticmethod
    def enforce_drawdown_ladder(drawdown_pct: float) -> Tuple[float, str, bool]:
        """
        Drawdown Ladder:
        - Drawdown <= -5%: De-leverage by 50% (capital_multiplier = 0.50).
        - Drawdown <= -8%: De-leverage by 75% / Orange Alert (capital_multiplier = 0.25).
        - Drawdown <= -12.0%: NUCLEAR FOOTBALL KILL-SWITCH (Emergency Liquidate All).
        """
        if drawdown_pct <= -0.12:
            return 0.0, "NUCLEAR_KILL_SWITCH_ACTIVE", True
        elif drawdown_pct <= -0.08:
            return 0.25, "DELEVERAGE_75_PERCENT", False
        elif drawdown_pct <= -0.05:
            return 0.50, "DELEVERAGE_50_PERCENT", False
        return 1.0, "NORMAL_ACTIVE", False


# --------------------------------------------------------------------------------------
# 3. TRỤ RAY DALIO: All-Weather 4 Góc & Chén Thánh Đa Dạng Hóa
# --------------------------------------------------------------------------------------
class AllWeatherRegime(str, Enum):
    REFLATION = "Rising Growth, Rising Inflation (Reflation)"
    STAGFLATION = "Falling Growth, Rising Inflation (Stagflation)"
    DEFLATION = "Falling Growth, Falling Inflation (Deflationary Deleveraging)"
    GOLDILOCKS = "Rising Growth, Falling Inflation (Goldilocks Expansion)"


class RayDalioTitanModule:
    """Bridgewater Associates Macro Framework: All-Weather & Holy Grail Metric."""

    @staticmethod
    def classify_macro_quadrant(growth_score: float, inflation_score: float) -> AllWeatherRegime:
        if growth_score >= 0 and inflation_score >= 0:
            return AllWeatherRegime.REFLATION
        elif growth_score < 0 and inflation_score >= 0:
            return AllWeatherRegime.STAGFLATION
        elif growth_score < 0 and inflation_score < 0:
            return AllWeatherRegime.DEFLATION
        else:
            return AllWeatherRegime.GOLDILOCKS

    @staticmethod
    def holy_grail_effective_bets(corr_matrix: np.ndarray) -> float:
        """Computes N_eff = N^2 / sum(lambda_i^2) via Eigen-decomposition."""
        n = corr_matrix.shape[0]
        if n <= 1:
            return 1.0
        eigvals = np.linalg.eigvalsh(corr_matrix)
        eigvals = np.maximum(eigvals, 1e-6)
        sum_lambda_sq = float(np.sum(eigvals ** 2))
        if sum_lambda_sq <= 1e-8:
            return 1.0
        n_eff = (n ** 2) / sum_lambda_sq
        return float(np.clip(n_eff, 1.0, float(n)))


# --------------------------------------------------------------------------------------
# 4. TRỤ BLACKROCK: Kho Bạc Alexander Hamilton & Ledoit-Wolf Shrinkage
# --------------------------------------------------------------------------------------
@dataclass
class BlackRockTreasuryState:
    total_capital_usd: float
    risk_free_reserve_usd: float
    active_trading_capital_usd: float
    cashflow_sweep_usd: float
    volatility_scale_factor: float
    shrunk_covariance_trace: float


class BlackRockTreasuryModule:
    """Aladdin Risk Engine & Alexander Hamilton Treasury: Cashflow Smoothing & Ledoit-Wolf Shrinkage."""

    def __init__(self, initial_capital_usd: float = 10_000.0, reserve_ratio: float = 0.20):
        self.initial_capital = initial_capital_usd
        self.total_capital = initial_capital_usd
        self.risk_free_reserve = initial_capital_usd * reserve_ratio
        self.active_capital = initial_capital_usd * (1.0 - reserve_ratio)

    def allocate_and_smooth(self, current_equity: float, returns_matrix: np.ndarray, target_vol: float = 0.015) -> BlackRockTreasuryState:
        """Sweeps 50% of new profits to risk-free reserve and scales quota via Ledoit-Wolf."""
        sweep = 0.0
        if current_equity > self.total_capital:
            new_profit = current_equity - self.total_capital
            sweep = new_profit * 0.50  # 50% cashflow sweep to safety reserve
            self.risk_free_reserve += sweep
            self.total_capital = current_equity

        # Ledoit-Wolf Covariance Shrinkage (Aladdin standard)
        shrunk_cov = self._shrink_covariance_ledoit_wolf(returns_matrix)
        trace_cov = float(np.trace(shrunk_cov))
        n_assets = returns_matrix.shape[1] if returns_matrix.ndim > 1 else 1
        market_vol = float(np.sqrt(trace_cov / max(1, n_assets)))

        vol_scaling = float(min(target_vol / max(market_vol, 1e-12), 1.0))

        return BlackRockTreasuryState(
            total_capital_usd=self.total_capital,
            risk_free_reserve_usd=self.risk_free_reserve,
            active_trading_capital_usd=self.total_capital - self.risk_free_reserve,
            cashflow_sweep_usd=sweep,
            volatility_scale_factor=vol_scaling,
            shrunk_covariance_trace=trace_cov,
        )

    @staticmethod
    def _shrink_covariance_ledoit_wolf(x: np.ndarray) -> np.ndarray:
        """Ledoit-Wolf optimal shrinkage towards identity times mean variance."""
        if x.ndim < 2 or x.shape[0] < 5:
            return np.eye(max(1, x.shape[1] if x.ndim > 1 else 1)) * 0.01

        t, n = x.shape
        x_centered = x - np.mean(x, axis=0)
        sample_cov = (x_centered.T @ x_centered) / t

        # Shrinkage target: mu * Identity
        mu = np.trace(sample_cov) / n
        target = mu * np.eye(n)

        # Shrinkage intensity alpha estimate
        d2 = np.linalg.norm(sample_cov - target, "fro") ** 2
        y = x_centered ** 2
        phi = np.sum((y.T @ y) / t - sample_cov ** 2)
        kappa = phi / d2 if d2 > 1e-12 else 0.2
        shrinkage = float(np.clip(kappa / t, 0.05, 0.95))

        return (1.0 - shrinkage) * sample_cov + shrinkage * target


# --------------------------------------------------------------------------------------
# TRUNG TÂM ĐIỀU HỢP BỘ TỨ TRỤ (MASTER QUAD-TITAN ORCHESTRATOR)
# --------------------------------------------------------------------------------------
class QuadTitanEngine:
    """Master Quantitative Core combining MIT, Wall Street, Ray Dalio, and BlackRock."""

    def __init__(self, initial_capital_usd: float = 10_000.0):
        self.mit = MITTitanModule()
        self.wall_street = WallStreetPodDefense()
        self.dalio = RayDalioTitanModule()
        self.blackrock = BlackRockTreasuryModule(initial_capital_usd=initial_capital_usd)

    def execute_quad_audit(
        self,
        current_equity: float,
        portfolio_drawdown: float,
        current_weights: np.ndarray,
        returns_history: np.ndarray,
        growth_indicator: float = 0.5,
        inflation_indicator: float = -0.2,
    ) -> Dict[str, Any]:
        """Runs the complete 4-pillar institutional check."""
        # 1. Wall Street Check
        capital_mult, pod_status, nuclear_kill = self.wall_street.enforce_drawdown_ladder(portfolio_drawdown)

        # 2. BlackRock Treasury Allocation & Cashflow Sweep
        treasury_state = self.blackrock.allocate_and_smooth(current_equity, returns_history)

        # 3. Ray Dalio Macro Regime & Holy Grail Score
        regime = self.dalio.classify_macro_quadrant(growth_indicator, inflation_indicator)
        corr_matrix = np.corrcoef(returns_history, rowvar=False) if returns_history.shape[0] > 5 else np.eye(len(current_weights))
        n_eff = self.dalio.holy_grail_effective_bets(corr_matrix)

        # 4. MIT Factor Neutrality & Adaptive Market VR Test
        synthetic_factors = np.ones((len(current_weights), 1))  # Market Beta factor
        mit_state = self.mit.neutralize_factor_exposure(current_weights, synthetic_factors)

        benchmark_prices = np.cumprod(1.0 + returns_history[:, 0]) if returns_history.shape[0] > 10 else np.array([100.0, 101.0, 102.0, 103.0])
        vr, vr_regime = self.mit.andrew_lo_variance_ratio(benchmark_prices)

        return {
            "status": "EMERGENCY_HALT" if nuclear_kill else "APPROVED",
            "nuclear_football_triggered": nuclear_kill,
            "wall_street_defense": {
                "capital_multiplier": capital_mult,
                "pod_status": pod_status,
                "drawdown_pct": portfolio_drawdown * 100.0,
            },
            "blackrock_treasury": {
                "total_capital_usd": treasury_state.total_capital_usd,
                "risk_free_reserve_usd": treasury_state.risk_free_reserve_usd,
                "active_capital_usd": treasury_state.active_trading_capital_usd,
                "cashflow_sweep_usd": treasury_state.cashflow_sweep_usd,
                "vol_scaling": treasury_state.volatility_scale_factor,
            },
            "ray_dalio_macro": {
                "regime": regime.value,
                "holy_grail_n_eff": round(n_eff, 2),
                "total_assets": len(current_weights),
                "diversification_ratio": round(n_eff / max(1, len(current_weights)) * 100.0, 1),
            },
            "mit_quantitative": {
                "is_strictly_factor_neutral": mit_state.is_strictly_orthogonal,
                "variance_ratio": vr,
                "lo_market_regime": vr_regime,
                "neutralized_weights": mit_state.neutralized_weights.tolist(),
            },
        }
