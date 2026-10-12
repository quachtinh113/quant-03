"""
Chiết Xuất Chiến Lược Giao Dịch Ray Dalio (Bridgewater Associates Foundation).
Cung cấp:
1. 4 Góc Phần Tư Vĩ Mô (All-Weather 4 Macro Quadrants):
   - Tăng trưởng Tăng (Rising Growth): Equities, Commodities, Corporate Debt.
   - Tăng trưởng Giảm (Falling Growth): Nominal Sovereign Bonds.
   - Lạm phát Tăng (Rising Inflation): Commodities, Gold, TIPS.
   - Lạm phát Giảm (Falling Inflation): Equities, Nominal Sovereign Bonds.
2. Nguyên lý Chén Thánh (Holy Grail of Investing):
   - Kết hợp 15+ dòng lợi nhuận độc lập, không tương quan (cross-correlation rho ~ 0).
   - Phân bổ rủi ro ngang bằng (Risk Parity / Equal Risk Contribution - ERC).
   - Khuếch đại tỷ số Sharpe không làm tăng Maximum Drawdown.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class MacroQuadrant(str, Enum):
    GROWTH_RISING = "GROWTH_RISING"
    GROWTH_FALLING = "GROWTH_FALLING"
    INFLATION_RISING = "INFLATION_RISING"
    INFLATION_FALLING = "INFLATION_FALLING"


@dataclass(frozen=True)
class MacroRegimeState:
    primary_quadrant: MacroQuadrant
    growth_score: float         # > 0 indicates growth accelerating, < 0 decelerating
    inflation_score: float      # > 0 indicates inflation rising, < 0 falling
    quadrant_probabilities: Dict[str, float]
    recommended_tilts: Dict[str, float]


@dataclass(frozen=True)
class RiskParityResult:
    weights: Dict[str, float]
    asset_volatilities: Dict[str, float]
    effective_bets: float          # N_eff = 1 / sum(w_i^2)
    portfolio_volatility: float
    holy_grail_sharpe_multiplier: float
    average_correlation: float


class RayDalioMacroEngine:
    """
    Cỗ máy phân tích chu kỳ kinh tế và phân bổ rủi ro All-Weather theo triết lý Ray Dalio.
    """

    # Ma trận phân bổ kinh điển All-Weather Bridgewater cho 4 môi trường vĩ mô
    BASE_QUADRANT_ALLOCATION = {
        MacroQuadrant.GROWTH_RISING: {
            "EQUITIES": 0.40,
            "COMMODITIES": 0.25,
            "CORPORATE_CREDIT": 0.20,
            "BONDS": 0.15,
        },
        MacroQuadrant.GROWTH_FALLING: {
            "EQUITIES": 0.10,
            "COMMODITIES": 0.05,
            "CORPORATE_CREDIT": 0.10,
            "BONDS": 0.75,
        },
        MacroQuadrant.INFLATION_RISING: {
            "EQUITIES": 0.10,
            "COMMODITIES": 0.35,
            "GOLD": 0.30,
            "TIPS": 0.25,
        },
        MacroQuadrant.INFLATION_FALLING: {
            "EQUITIES": 0.45,
            "COMMODITIES": 0.05,
            "CORPORATE_CREDIT": 0.20,
            "BONDS": 0.30,
        },
    }

    @staticmethod
    def classify_macro_quadrant(
        growth_indicator: float,
        inflation_indicator: float
    ) -> MacroRegimeState:
        """
        Phân loại môi trường vĩ mô dựa trên 2 vector:
        1. Gia tốc tăng trưởng kinh tế (Growth Momentum: GDP, PMI, Employment)
        2. Gia tốc lạm phát (Inflation Momentum: CPI, PPI, Yield Breakeven)
        """
        # Xác định góc phần tư chi phối
        if abs(growth_indicator) >= abs(inflation_indicator):
            if growth_indicator >= 0:
                primary = MacroQuadrant.GROWTH_RISING
            else:
                primary = MacroQuadrant.GROWTH_FALLING
        else:
            if inflation_indicator >= 0:
                primary = MacroQuadrant.INFLATION_RISING
            else:
                primary = MacroQuadrant.INFLATION_FALLING

        # Tính xác suất mềm (Softmax probabilities) giữa 4 trạng thái
        scores = np.array([
            growth_indicator - inflation_indicator * 0.2,   # Growth Rising
            -growth_indicator - inflation_indicator * 0.2,  # Growth Falling
            inflation_indicator - growth_indicator * 0.2,   # Inflation Rising
            -inflation_indicator + growth_indicator * 0.2,  # Inflation Falling
        ])
        exp_scores = np.exp(np.clip(scores, -5.0, 5.0))
        probs = exp_scores / np.sum(exp_scores)

        prob_dict = {
            MacroQuadrant.GROWTH_RISING.value: float(probs[0]),
            MacroQuadrant.GROWTH_FALLING.value: float(probs[1]),
            MacroQuadrant.INFLATION_RISING.value: float(probs[2]),
            MacroQuadrant.INFLATION_FALLING.value: float(probs[3]),
        }

        # Tính tỷ trọng khuyến nghị All-Weather được pha trộn theo xác suất (Expected Allocation)
        tilts: Dict[str, float] = {}
        for q_enum, p in zip(MacroQuadrant, probs):
            q_alloc = RayDalioMacroEngine.BASE_QUADRANT_ALLOCATION.get(q_enum, {})
            for asset, weight in q_alloc.items():
                tilts[asset] = tilts.get(asset, 0.0) + weight * float(p)

        # Chuẩn hóa tổng = 1.0
        total_tilt = sum(tilts.values())
        if total_tilt > 0:
            for k in tilts:
                tilts[k] = round(tilts[k] / total_tilt, 4)

        return MacroRegimeState(
            primary_quadrant=primary,
            growth_score=float(growth_indicator),
            inflation_score=float(inflation_indicator),
            quadrant_probabilities=prob_dict,
            recommended_tilts=tilts
        )

    @staticmethod
    def calculate_holy_grail_risk_parity(
        returns_df: pd.DataFrame,
        quadrant_tilt: Optional[Dict[str, float]] = None
    ) -> RiskParityResult:
        """
        Ray Dalio Holy Grail & Risk Parity Allocator:
        Phân bổ rủi ro ngang bằng sao cho mỗi tài sản đóng góp mức độ biến động ngang nhau:
        w_i = (1 / sigma_i) / sum(1 / sigma_j)

        Sau đó tính toán 'Chén Thánh':
        Hệ số khuếch đại Sharpe = sqrt(N) / sqrt(1 + (N - 1) * rho_avg)
        """
        assets = list(returns_df.columns)
        n_assets = len(assets)
        if n_assets == 0:
            raise ValueError("Returns DataFrame has no asset columns.")

        # Tính độ biến động mẫu (Sample volatility)
        vols = returns_df.std(ddof=1).values
        # Tránh chia cho 0
        vols = np.maximum(vols, 1e-8)

        # Trọng số đảo biến động (Inverse Volatility Weights)
        inv_vols = 1.0 / vols
        raw_weights = inv_vols / np.sum(inv_vols)

        # Nếu có macro tilt từ 4 góc phần tư Dalio, áp dụng kết hợp
        if quadrant_tilt:
            tilted_weights = np.zeros(n_assets)
            for idx, asset in enumerate(assets):
                tilt = quadrant_tilt.get(asset, 1.0 / n_assets)
                tilted_weights[idx] = raw_weights[idx] * (1.0 + tilt)
            weights = tilted_weights / np.sum(tilted_weights)
        else:
            weights = raw_weights

        # Ma trận hiệp phương sai mẫu
        cov_matrix = returns_df.cov().values
        # Biến động danh mục: sigma_p = sqrt(w^T * Sigma * w)
        port_var = float(weights.T @ cov_matrix @ weights)
        port_vol = float(np.sqrt(max(port_var, 1e-12)))

        # Tính tương quan trung bình (Average Cross-Correlation)
        corr_matrix = returns_df.corr().values
        mask = np.triu(np.ones((n_assets, n_assets), dtype=bool), k=1)
        if np.sum(mask) > 0:
            avg_corr = float(np.mean(corr_matrix[mask]))
        else:
            avg_corr = 0.0

        # Số lượng cược độc lập hiệu dụng (Effective Number of Bets): N_eff = 1 / sum(w_i^2)
        effective_bets = float(1.0 / np.sum(weights ** 2))

        # Công thức Chén thánh của Ray Dalio:
        # Tỷ số Sharpe được nhân lên khi số dòng không tương quan N tăng:
        # Multiplier = sqrt(N) / sqrt(1 + (N - 1) * rho)
        n_eff_clamped = max(1.0, effective_bets)
        avg_corr_clamped = np.clip(avg_corr, -0.99, 0.99)
        sharpe_mult = float(
            np.sqrt(n_eff_clamped) / np.sqrt(max(0.01, 1.0 + (n_eff_clamped - 1.0) * avg_corr_clamped))
        )

        weights_dict = {assets[i]: float(weights[i]) for i in range(n_assets)}
        vols_dict = {assets[i]: float(vols[i]) for i in range(n_assets)}

        return RiskParityResult(
            weights=weights_dict,
            asset_volatilities=vols_dict,
            effective_bets=round(effective_bets, 2),
            portfolio_volatility=port_vol,
            holy_grail_sharpe_multiplier=round(sharpe_mult, 3),
            average_correlation=round(avg_corr, 4)
        )
