"""
The Federal Reserve: Dynamic Quantitative Easing (QE) & Quantitative Tightening (QT) Allocator
Monitors market volatility and cross-pod performance:
- Calm markets + high Sharpe: QE Policy -> Expands lot limits and leverages capital.
- Turbulent markets + volatility spike: QT Policy -> Slashes lot quotas and hikes capital requirements.
"""

from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
from .interest_rate_matrix import ledoit_wolf_covariance_shrinkage


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
