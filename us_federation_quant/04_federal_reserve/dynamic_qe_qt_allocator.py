"""
The Federal Reserve: Dynamic Quantitative Easing (QE) & Quantitative Tightening (QT) Allocator
Monitors market volatility and cross-pod performance:
- Calm markets + high Sharpe: QE Policy -> Expands lot limits and leverages capital.
- Turbulent markets + volatility spike: QT Policy -> Slashes lot quotas and hikes capital requirements.
"""

from typing import Dict, Any
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
