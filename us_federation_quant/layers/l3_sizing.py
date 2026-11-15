"""l3_sizing: tầng gộp từ emergency_liquidity_fund.py, interest_rate_matrix.py, dynamic_qe_qt_allocator.py, quad_titan_engine.py."""
from __future__ import annotations

from typing import Dict, Any
import numpy as np
import pandas as pd
from typing import Tuple
from typing import Dict, Any, Optional, List, Tuple
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ====================================================================================================
# 03_portfolio/federal_reserve/emergency_liquidity_fund.py  —  The Federal Reserve: Emergency Liquidity Fund & Profit Sweeping Pool
# ====================================================================================================




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


# ====================================================================================================
# 03_portfolio/federal_reserve/interest_rate_matrix.py  —  The Federal Reserve: Interest Rate Matrix & Ledoit-Wolf Covariance Denoising
# ====================================================================================================




def ledoit_wolf_covariance_shrinkage(X: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Computes analytical Ledoit-Wolf covariance matrix shrinkage:
    Sigma_shrunk = (1 - delta) * S + delta * F
    where F = (trace(S)/p) * Identity.
    """
    n, p = X.shape
    if n < 2:
        return np.eye(p), 1.0

    X_centered = X - np.mean(X, axis=0)
    S = (X_centered.T @ X_centered) / (n - 1)

    mu = np.trace(S) / p
    F = mu * np.eye(p)

    d2 = np.sum((S - F) ** 2)

    b2 = 0.0
    for i in range(n):
        row = X_centered[i:i+1, :]
        outer = row.T @ row
        b2 += np.sum((outer - S) ** 2)
    b2 /= (n ** 2)

    b2 = min(b2, d2)
    delta = 0.0 if d2 == 0 else max(0.0, min(1.0, b2 / d2))

    S_shrunk = (1.0 - delta) * S + delta * F
    return S_shrunk, float(round(delta, 4))


# ====================================================================================================
# 03_portfolio/federal_reserve/dynamic_qe_qt_allocator.py  —  The Federal Reserve: Dynamic Quantitative Easing (QE) & Quantitative Tightening (QT) Allocator
# ====================================================================================================




class FederalReserveAllocator:
    """
    Independent Central Bank managing leverage and capital liquidity quotas across 50 states.
    """

    def __init__(self, base_total_capital: float = 10_000_000.0):
        self.total_capital = base_total_capital
        self.current_policy = "NEUTRAL"

    def determine_policy_stance(self, market_volatility: float, avg_pod_sharpe: float = 2.0) -> Dict[str, Any]:
        """
        Calculates whether FED conducts QE (expansion) or QT (contraction).
        """
        if market_volatility > 0.025: # High stress
            policy = "QT_QUANTITATIVE_TIGHTENING"
            multiplier = 0.5 # Slash quotas by 50%
        elif market_volatility < 0.010 and avg_pod_sharpe >= 1.5:
            policy = "QE_QUANTITATIVE_EASING"
            multiplier = 1.25 # Boost quotas by 25%
        else:
            policy = "NEUTRAL"
            multiplier = 1.0

        self.current_policy = policy
        return {
            "policy": policy,
            "quota_multiplier": multiplier,
            "market_volatility": market_volatility,
            "avg_pod_sharpe": avg_pod_sharpe
        }

    def allocate_state_quotas(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """
        Allocates capital quotas to states using Ledoit-Wolf denoised inverse-variance weights.
        """
        cols = list(returns_df.columns)
        p = len(cols)
        if p == 0:
            return {}

        cov_matrix, delta = ledoit_wolf_covariance_shrinkage(returns_df.values)
        variances = np.diag(cov_matrix)
        variances = np.where(variances <= 0, 1e-6, variances)

        inv_vars = 1.0 / variances
        weights = inv_vars / np.sum(inv_vars)

        quotas = {}
        for col, w in zip(cols, weights):
            quotas[col] = float(round(w * self.total_capital, 2))

        return quotas

    # ==================================================================================
    # NỐI KẾT NGÀY 26/09/2026 — TỐI ƯU HÓA CÓ RÀNG BUỘC THỰC TẾ
    # ==================================================================================
    def allocate_state_quotas_constrained(
        self,
        returns_df: pd.DataFrame,
        max_states: int = 12,
        min_quota_fraction: float = 0.02,
        max_quota_fraction: float = 0.25,
        correlation_groups: Dict[str, str] = None,
        group_caps: Dict[str, float] = None,
        previous_quotas: Dict[str, float] = None,
        transaction_cost_bps: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Phân bổ hạn mức có ràng buộc thực tế — bản nâng cấp của `allocate_state_quotas`.

        VÌ SAO CẦN BẢN NÀY
        ------------------
        `allocate_state_quotas` chia vốn theo tỉ lệ nghịch phương sai trên **toàn bộ**
        State. Cách đó đúng về mặt toán học nhưng bỏ qua bốn ràng buộc mà sàn áp đặt:

          1. **Hạn mức quá nhỏ để đặt lệnh.** Chia 10 triệu cho 50 State cho hạn mức mà
             với lô tối thiểu 0.01 là không mở nổi vị thế có nghĩa.
          2. **Không trần số State.** Càng nhiều pod càng nhiều chi phí vận hành và càng
             khó giám sát.
          3. **Không chặn exposure chồng lấn.** XAUUSD và XAGUSD đều là kim loại quý —
             chia vốn cho cả hai không phải phân tán rủi ro mà là nhân đôi một cược.
          4. **Không tính chi phí dịch chuyển.** Tái phân bổ mỗi kỳ tốn tiền thật.

        Hàm này giải bài toán có cả bốn ràng buộc bằng
        `01_mit_foundations/constrained_portfolio_optimizer.py`.

        ⚠️ Hàm cũ **không bị thay đổi**. Đây là đường bổ sung để chọn có ý thức, vì bài
        toán có ràng buộc là phi lồi nên chậm hơn và có thể báo bất khả thi.

        :return: dict gồm `quotas`, `n_states`, `is_globally_optimal`, `violations`,
                 `method` — luôn nêu rõ nghiệm có bảo đảm tối ưu hay chỉ là heuristic.
        """
        import importlib
        import sys
        from pathlib import Path

        _workspace = Path(__file__).resolve().parent.parent.parent
        if str(_workspace) not in sys.path:
            sys.path.insert(0, str(_workspace))
        _opt_mod = importlib.import_module(
            "quant_research_hub.01_mit_foundations.constrained_portfolio_optimizer"
        )

        cols = list(returns_df.columns)
        if not cols:
            return {"quotas": {}, "n_states": 0, "is_globally_optimal": False,
                    "violations": ["Không có State nào trong dữ liệu."], "method": "empty"}

        cov_matrix, _delta = ledoit_wolf_covariance_shrinkage(returns_df.values)
        expected_returns = returns_df.mean().to_numpy()

        index_of = {name: i for i, name in enumerate(cols)}
        group_of = {}
        if correlation_groups:
            group_of = {
                index_of[name]: group
                for name, group in correlation_groups.items()
                if name in index_of
            }

        previous_weights = None
        if previous_quotas and self.total_capital > 0:
            previous_weights = np.array(
                [previous_quotas.get(name, 0.0) / self.total_capital for name in cols]
            )

        constraints = _opt_mod.PortfolioConstraints(
            budget=1.0,
            long_only=True,
            min_weight=min_quota_fraction,
            max_weight=max_quota_fraction,
            max_positions=max_states,
            group_caps=group_caps or {},
            group_of=group_of,
        )
        optimizer = _opt_mod.ConstrainedPortfolioOptimizer(
            risk_aversion=3.0, transaction_cost_bps=transaction_cost_bps
        )
        result = optimizer.optimize(
            expected_returns, cov_matrix, constraints, previous_weights=previous_weights
        )

        quotas = {
            name: float(round(weight * self.total_capital, 2))
            for name, weight in zip(cols, result.weights)
            if abs(weight) > 1e-10
        }

        return {
            "quotas": quotas,
            "n_states": result.n_positions,
            "expected_return": result.expected_return,
            "volatility": result.volatility,
            "turnover": result.turnover,
            "is_globally_optimal": result.is_globally_optimal,
            "violations": result.violations,
            "method": result.method,
        }

    # ==================================================================================
    # ROBERT CARVER (pysystemtrade) SYSTEMATIC VOLATILITY TARGETING & IDM ENGINE
    # ==================================================================================
    def allocate_carver_state_quotas(
        self,
        returns_df: pd.DataFrame,
        previous_quotas: Optional[Dict[str, float]] = None,
        market_volatility: float = 0.012,
        avg_pod_sharpe: float = 2.0,
        custom_weights: Optional[Dict[str, float]] = None,
        buffer_fraction: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Allocates capital and daily cash volatility targets across state pods
        using Robert Carver's Systematic Portfolio Theory (pysystemtrade).

        Incorporates:
        1. Fed QE/QT Policy Stance (modulating annual target volatility).
        2. Ledoit-Wolf Covariance Denoising & Shrinkage.
        3. Instrument Diversification Multiplier (IDM) for multi-asset pods.
        4. Position / Quota Buffering (+/- 10%) to eliminate turnover churn.
        """
        cols = list(returns_df.columns)
        n = len(cols)
        if n == 0:
            return {
                "quotas": {},
                "cash_vol_targets": {},
                "idm": 1.0,
                "policy": "NEUTRAL",
                "annual_target_vol_pct": 16.0,
                "total_allocated": 0.0,
                "n_states": 0,
            }

        # 1. Determine Fed Policy & Carver Volatility Target
        stance = self.determine_policy_stance(market_volatility=market_volatility, avg_pod_sharpe=avg_pod_sharpe)
        policy = stance["policy"]
        quota_mult = stance["quota_multiplier"]

        carver_engine = CarverQEAllocationEngine(buffer_fraction=buffer_fraction)
        annual_target_vol = carver_engine.get_policy_adjusted_vol_target(policy)
        daily_target_vol = (annual_target_vol / 100.0) / carver_engine.daily_vol_factor

        # 2. Covariance Shrinkage & IDM Computation
        cov_matrix, _delta = ledoit_wolf_covariance_shrinkage(returns_df.values)

        if custom_weights:
            w_raw = np.array([custom_weights.get(c, 1.0 / n) for c in cols], dtype=float)
        else:
            variances = np.diag(cov_matrix)
            variances = np.where(variances <= 1e-8, 1e-8, variances)
            w_raw = 1.0 / variances

        weights = w_raw / np.sum(w_raw)
        idm, corr_matrix = carver_engine.compute_idm_from_covariance(cov_matrix, weights=weights)

        # 3. Calculate Quotas & Cash Vol Targets with Trade Buffering
        quotas: Dict[str, float] = {}
        cash_vol_targets: Dict[str, float] = {}
        buffered_states: List[str] = []

        for i, col in enumerate(cols):
            w_i = float(weights[i])
            cash_vol = float(self.total_capital * daily_target_vol * w_i * idm * quota_mult)
            cash_vol_targets[col] = round(cash_vol, 2)

            raw_quota = float(self.total_capital * w_i * quota_mult)
            prev_q = previous_quotas.get(col, 0.0) if previous_quotas else 0.0
            buffered_q, was_buffered = carver_engine.apply_position_buffer(prev_q, raw_quota)
            if was_buffered:
                buffered_states.append(col)

            quotas[col] = round(buffered_q, 2)

        return {
            "policy": policy,
            "quota_multiplier": quota_mult,
            "annual_target_vol_pct": annual_target_vol,
            "daily_target_vol_pct": round(daily_target_vol * 100.0, 4),
            "idm": round(idm, 3),
            "quotas": quotas,
            "cash_vol_targets": cash_vol_targets,
            "buffered_states": buffered_states,
            "total_allocated": round(sum(quotas.values()), 2),
            "n_states": n,
        }


class CarverQEAllocationEngine:
    """
    Robert Carver (pysystemtrade / Man AHL) Systematic Portfolio Allocation Engine
    coupled with Federal Reserve Dynamic QE/QT Policy Stance.

    Implements:
    1. Dynamic Annual Volatility Target:
       - QE: 20.0% (Calculated Risk Expansion)
       - NEUTRAL: 16.0% (Carver Macro Benchmark)
       - QT: 8.0% (Risk Contraction & Capital Defense)
    2. Ledoit-Wolf Covariance to Correlation Matrix -> Instrument Diversification Multiplier (IDM):
       IDM = 1.0 / sqrt(w^T * Corr * w), bounded in [1.0, 2.5]
    3. Daily Cash Volatility Target ($):
       CashVolTarget_i = TotalCapital * DailyVolTarget * w_i * IDM * QuotaMultiplier
    4. Position / Quota Buffering (+/- 10%):
       Avoids churn and transaction friction if new quota is within buffer bandwidth of previous quota.
    """

    def __init__(
        self,
        base_annual_target_vol_pct: float = 16.0,
        default_idm: float = 1.40,
        buffer_fraction: float = 0.10,
        trading_days_per_year: int = 256,
    ):
        self.base_annual_target_vol_pct = base_annual_target_vol_pct
        self.default_idm = default_idm
        self.buffer_fraction = buffer_fraction
        self.trading_days_per_year = trading_days_per_year
        self.daily_vol_factor = np.sqrt(trading_days_per_year)

    def get_policy_adjusted_vol_target(self, policy: str) -> float:
        """
        Adjusts annual target volatility based on Fed QE/QT policy stance:
        - QE: 20.0% (Risk expansion during high Sharpe & calm volatility)
        - NEUTRAL: 16.0% (Carver systematic baseline)
        - QT: 8.0% (Aggressive risk reduction during turbulent markets)
        """
        if "QE" in policy.upper():
            return 20.0
        elif "QT" in policy.upper():
            return 8.0
        else:
            return self.base_annual_target_vol_pct

    def compute_idm_from_covariance(
        self,
        cov_matrix: np.ndarray,
        weights: Optional[np.ndarray] = None
    ) -> Tuple[float, np.ndarray]:
        """
        Converts covariance to correlation matrix and calculates Robert Carver's IDM:
        IDM = 1.0 / sqrt(w^T * Corr * w)
        Clamped to [1.0, 2.5] institutional bounds.
        """
        n = cov_matrix.shape[0]
        if n <= 1:
            return 1.0, np.eye(n)

        std_devs = np.sqrt(np.diag(cov_matrix))
        std_devs = np.where(std_devs <= 1e-8, 1e-8, std_devs)
        outer_std = np.outer(std_devs, std_devs)
        corr_matrix = cov_matrix / outer_std
        np.fill_diagonal(corr_matrix, 1.0)
        corr_matrix = np.clip(corr_matrix, -1.0, 1.0)

        if weights is None:
            w = np.ones(n) / n
        else:
            w = weights / np.sum(weights)

        portfolio_var_factor = float(np.dot(w.T, np.dot(corr_matrix, w)))
        if portfolio_var_factor <= 0.0:
            return 1.0, corr_matrix

        idm = 1.0 / np.sqrt(portfolio_var_factor)
        idm = float(np.clip(idm, 1.0, 2.5))
        return idm, corr_matrix

    def apply_position_buffer(
        self,
        current_val: float,
        target_val: float
    ) -> Tuple[float, bool]:
        """
        Carver Trade Buffering:
        If target value is within +/- buffer_fraction of current value,
        retains current value to prevent transaction fees, spread churn and impact.
        Returns (buffered_value, is_buffered).
        """
        if current_val <= 0.0:
            return target_val, False

        diff = abs(target_val - current_val)
        threshold = self.buffer_fraction * current_val

        if diff <= threshold:
            return current_val, True
        return target_val, False


# ====================================================================================================
# 03_portfolio/federal_reserve/quad_titan_engine.py  —  ========================================================================================
# ====================================================================================================





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


# ====================================================================================================
# TOÁN LOT THUẦN (từ live_federation_runner): trần rủi ro cứng + ATR dollar sizing
# Nhận spec đã đọc bởi L1 (SymbolSpec / symbol_info thô); không gọi MT5. golden: tests/test_golden_symbol_spec_sizing.py
# ====================================================================================================

def hard_risk_cap_lot(sym_info, symbol, raw_lot, sl_distance_price, max_risk_usd, *, index_cap_usd, universal_cap_usd):
    """Khống chế mức lỗ tối đa tại SL không vượt max_risk_usd; làm tròn XUỐNG theo volume_step."""
    if not sym_info or sl_distance_price <= 0:
        return sym_info.volume_min if sym_info else 0.01

    trade_tick_size = float(getattr(sym_info, "trade_tick_size", 0.0) or 0.0)
    trade_tick_value = float(getattr(sym_info, "trade_tick_value", 0.0) or 0.0)
    volume_step = float(getattr(sym_info, "volume_step", 0.01) or 0.01)
    volume_min = float(getattr(sym_info, "volume_min", 0.01) or 0.01)
    volume_max = float(getattr(sym_info, "volume_max", 100.0) or 100.0)

    if trade_tick_size <= 0:
        trade_tick_size = getattr(sym_info, "point", 0.0001) or 0.0001
    if trade_tick_value <= 0:
        trade_tick_value = 1.0

    ticks_in_sl = sl_distance_price / trade_tick_size
    loss_per_lot = ticks_in_sl * trade_tick_value
    if loss_per_lot <= 0:
        return volume_min

    sym_clean = symbol.upper().replace("M", "")
    is_index = any(idx in sym_clean for idx in ["USTEC", "US30", "US100", "US500", "HK50"])
    cap_limit = index_cap_usd if is_index else universal_cap_usd
    target_cap = min(max_risk_usd, cap_limit)
    max_allowed_lot = target_cap / loss_per_lot
    capped_lot = min(raw_lot, max_allowed_lot)

    if volume_step > 0:
        step_count = int(round(capped_lot / volume_step, 6))
        final_lot = step_count * volume_step
    else:
        final_lot = capped_lot

    final_lot = max(volume_min, min(round(final_lot, 2), volume_max))
    return final_lot


def risk_adjusted_lot(symbol, sl_points, max_risk_usd, spec_read, *, universal_cap_usd):
    """ATR Dollar Sizing với Hard Risk Cap. spec_read: SymbolSpec (info thô hoặc spec dict của mgr).

    Trả về (lot, LogLine) để caller ghi log đúng như bản cũ.
    """
    from us_federation_quant.Document.contracts import LogLine
    s_info = spec_read.info

    if s_info is not None:
        trade_tick_value = float(getattr(s_info, "trade_tick_value", 0.0) or 0.0)
        trade_tick_size = float(getattr(s_info, "trade_tick_size", 0.0) or 0.0)
        point = float(getattr(s_info, "point", 0.0) or 0.0)
        volume_min = float(getattr(s_info, "volume_min", 0.01) or 0.01)
        volume_max = float(getattr(s_info, "volume_max", 100.0) or 100.0)
        volume_step = float(getattr(s_info, "volume_step", 0.01) or 0.01)
    else:
        spec = spec_read.spec
        point = float(spec.get("point", 0.0001) or 0.0001)
        trade_tick_size = float(spec.get("tick_size", point) or point)
        trade_tick_value = float(spec.get("tick_value", 1.0) or 1.0)
        volume_min = float(spec.get("volume_min", 0.01) or 0.01)
        volume_max = float(spec.get("volume_max", 100.0) or 100.0)
        volume_step = float(spec.get("volume_step", 0.01) or 0.01)

    if trade_tick_size > 0 and point > 0:
        tick_value_per_point = trade_tick_value * (point / trade_tick_size)
    else:
        tick_value_per_point = trade_tick_value

    if tick_value_per_point <= 0:
        tick_value_per_point = 1.0

    sym_clean = symbol.upper().replace("M", "")
    effective_risk_usd = min(float(max_risk_usd), universal_cap_usd)

    safe_sl_points = max(float(sl_points), 10.0)
    dollar_risk_per_lot = safe_sl_points * tick_value_per_point
    raw_lot = effective_risk_usd / max(dollar_risk_per_lot, 1e-6)

    is_index = any(idx in sym_clean for idx in ["USTEC", "US30", "US100", "HK50"])
    if is_index:
        raw_lot = float(np.clip(raw_lot, 0.01, 0.03))

    if volume_step > 0:
        steps = int(round(raw_lot / volume_step, 6))
        normalized_lot = steps * volume_step
    else:
        normalized_lot = raw_lot

    normalized_lot = max(volume_min, min(normalized_lot, volume_max))
    normalized_lot = round(normalized_lot, 2)

    expected_sl_loss = dollar_risk_per_lot * normalized_lot
    if expected_sl_loss > effective_risk_usd and normalized_lot > volume_min:
        normalized_lot = max(volume_min, round(normalized_lot - volume_step, 2))
        expected_sl_loss = dollar_risk_per_lot * normalized_lot

    return normalized_lot, LogLine("info",
        f"📐 [VOLATILITY ATR SIZING] {symbol}: sl_points={safe_sl_points:.1f}, "
        f"trade_tick_value={trade_tick_value}, tick_val_per_point={tick_value_per_point:.5f}, "
        f"max_risk=${effective_risk_usd:.2f} -> raw={raw_lot:.4f}L, normalized={normalized_lot:.2f}L "
        f"(Expected SL Loss: ${expected_sl_loss:.2f}, Index Cap: {is_index})")


# ====================================================================================================
# SIZING LỆNH VÀO, HAI GIAI ĐOẠN (từ scan_and_route_state_proposals). Risk desk (L4) chen giữa hai giai đoạn.
# Đọc dữ liệu (tick) và các hàm đọc spec (lot_fn/cap_fn) được TIÊM vào; L3 không gọi MT5. golden: tests/test_golden_scan_pipeline.py
# ====================================================================================================

def size_entry(*, action, market_df, tick, sym_info, symbol, ml_scale, max_index_risk_usd, max_hard_risk_usd,
               elite_symbols, booster_multiplier, lot_fn, cap_fn, emit):
    """Giai đoạn A: giá vào, ATR14, SL/TP, lot (Alpha Booster rồi ML scale, mỗi bước cap lại). Trả về SizingPlan."""
    from us_federation_quant.Document.contracts import LogLine, SizingPlan
    if tick and tick.get("ask") and tick.get("bid"):
        current_price = float(tick["ask"] if action == "BUY" else tick["bid"])
    else:
        current_price = float(market_df["close"].iloc[-1])

    tr = np.maximum(
        market_df["high"] - market_df["low"],
        np.maximum(
            abs(market_df["high"] - market_df["close"].shift(1)),
            abs(market_df["low"] - market_df["close"].shift(1))
        )
    )
    atr_14 = float(tr.rolling(14).mean().iloc[-1])
    if np.isnan(atr_14) or atr_14 <= 0:
        atr_14 = float(market_df["high"].iloc[-1] - market_df["low"].iloc[-1])
    if atr_14 <= 0:
        atr_14 = current_price * 0.005

    pt = getattr(sym_info, "point", 0.0001) or 0.0001
    stops_level = getattr(sym_info, "trade_stops_level", 0) or 0
    spread = getattr(sym_info, "spread", 0) or 0
    min_stop_dist = (stops_level + spread + 5) * pt
    min_point_floor = 150.0 * pt

    # Dynamic ATR Buffer cho Chỉ số Mỹ (>= 2.2 * ATR14): nới SL TRƯỚC hàm tính lot để lot tự giảm, giữ Hard Risk Cap
    actual_sym_clean = symbol.upper().replace("M", "")
    is_index = any(idx in actual_sym_clean for idx in ["USTEC", "US30", "US100", "US500", "HK50"])

    if is_index:
        sl_dist = max(2.2 * atr_14, min_point_floor, min_stop_dist)
    else:
        sl_dist = max(1.8 * atr_14, min_point_floor, min_stop_dist)

    tp_dist = max(2.5 * atr_14, sl_dist * 1.5)
    sl_points = max(sl_dist / max(pt, 1e-6), 10.0)

    symbol_max_risk = max_index_risk_usd if is_index else max_hard_risk_usd
    lots = lot_fn(symbol=symbol, sl_points=sl_points, max_risk_usd=symbol_max_risk)

    # Carver Tier-A Elite Alpha Booster (x1.6): luôn chặn trên bởi Universal Hard Risk Cap
    is_elite = any(actual_sym_clean == elite or actual_sym_clean.startswith(elite) for elite in elite_symbols)
    if is_elite and not is_index:
        booster = booster_multiplier
        boosted_lot = round(lots * booster, 2)
        lots = cap_fn(symbol, boosted_lot, sl_dist, max_risk_usd=symbol_max_risk)
        emit(LogLine("info",
            f"🚀 [ALPHA BOOSTER] {symbol} thuộc nhóm Elite Alpha -> "
            f"Áp dụng x{booster} đòn bẩy: {boosted_lot}L -> Capped: {lots}L (Trần rủi ro <= ${symbol_max_risk:.2f})."))

    if ml_scale != 1.0:
        lots = round(lots * ml_scale, 2)
        lots = cap_fn(symbol, lots, sl_dist, max_risk_usd=symbol_max_risk)

    return SizingPlan(current_price=current_price, atr_14=atr_14, sl_dist=sl_dist, tp_dist=tp_dist,
                      sl_points=sl_points, symbol_max_risk=symbol_max_risk, is_index=is_index, lots=lots)


def finalize_entry(plan, *, symbol, lots_cleared, sym_info, action, normalize_fn, cap_fn):
    """Giai đoạn B (sau risk desk): chuẩn hóa lot theo broker, cap cuối $15/$60, rồi mức SL/TP tuyệt đối."""
    from us_federation_quant.Document.contracts import EntryLevels
    lots = normalize_fn(symbol, lots_cleared)
    lots = cap_fn(symbol, lots, plan.sl_dist, max_risk_usd=plan.symbol_max_risk)

    digits = getattr(sym_info, "digits", 2) or 2
    if action == "BUY":
        target_sl = round(plan.current_price - plan.sl_dist, digits)
        target_tp = round(plan.current_price + plan.tp_dist, digits)
    else:
        target_sl = round(plan.current_price + plan.sl_dist, digits)
        target_tp = round(plan.current_price - plan.tp_dist, digits)
    return EntryLevels(lots=lots, sl=target_sl, tp=target_tp)
