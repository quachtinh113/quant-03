"""
HỆ THỐNG ĐỊNH LƯỢNG HỢP NHẤT: MIT QUANT RESEARCH + MATRIX COMPENSATOR + RAY DALIO ALL-WEATHER
(Unified MIT-Dalio Tactical & Strategic Pipeline)

Quy trình 5 Bước Chuẩn Mực Hàn Lâm:
1. MIT Lo-MacKinlay AMH: Kiểm định Tỷ số Phương sai VR(q) chẩn đoán bước đi ngẫu nhiên vs xu hướng/đảo chiều.
2. Ray Dalio 4 Macro Quadrants: Phân loại chu kỳ vĩ mô (Tăng trưởng x Lạm phát) và xác lập Risk Tilt.
3. Ray Dalio Holy Grail Risk Parity: Phân bổ rủi ro ngang bằng và khuếch đại Sharpe theo số dòng độc lập N_eff.
4. MIT Matrix Compensator: Chiếu trực giao vào Không gian Không (Nullspace) triệt tiêu 100% rủi ro factor hệ thống.
5. Peter Kempthorne Givens Rotation: Khử tương quan cặp chéo tạo spread tĩnh tối thiểu phương sai.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from .ray_dalio_engine import (
    RayDalioMacroEngine,
    MacroQuadrant,
    MacroRegimeState,
    RiskParityResult,
)
from .mit_matrix_compensator import (
    MITMatrixCompensator,
    VarianceRatioAudit,
    MatrixHedgeAudit,
)


@dataclass(frozen=True)
class UnifiedAllocationVerdict:
    """Kết quả phân bổ định lượng hợp nhất MIT - Ray Dalio - FED đã được kiểm định."""
    assets: List[str]
    raw_weights: Dict[str, float]
    compensating_hedge_weights: Dict[str, float]
    final_neutralized_weights: Dict[str, float]
    factor_leakage_max: float
    is_factor_neutral: bool
    macro_regime: MacroRegimeState
    risk_parity_metrics: RiskParityResult
    primary_variance_ratio: VarianceRatioAudit
    givens_pair_hedges: Dict[str, Dict[str, float]]
    fed_liquidity_multiplier: float
    fed_policy_summary: Optional[Dict[str, Any]]
    verdict_status: str  # 'AUDITED_AND_APPROVED', 'REJECTED_FACTOR_LEAKAGE', 'CAUTION_RANDOM_WALK'


class UnifiedMITDalioPipeline:
    """
    Đầu não tích hợp toàn diện: Nền tảng học thuyết MIT + Phép bù trừ ma trận + Chiến lược Ray Dalio + Quyết sách FED.
    Không lan man — 100% công thức toán học và kiểm định nghiêm ngặt.
    """

    @classmethod
    def synthesize_portfolio_allocation(
        cls,
        price_history_df: pd.DataFrame,
        factor_matrix: np.ndarray,
        growth_indicator: float = 0.0,
        inflation_indicator: float = 0.0,
        fed_assessment: Optional[Dict[str, Any]] = None,
        tactical_alpha_signals: Optional[Dict[str, float]] = None,
        alpha_tactical_weight: float = 0.30,
        factor_leakage_tol: float = 1e-6
    ) -> UnifiedAllocationVerdict:
        """
        Thực hiện quy trình hợp nhất định lượng hoàn chỉnh.
        Nếu truyền vào fed_assessment từ CentralBankQuantitativeMaster, các chỉ số vĩ mô tăng trưởng/lạm phát
        và hệ số đòn bẩy thanh khoản trung ương sẽ được tự động đồng bộ hóa.


        Args:
            price_history_df: DataFrame giá đóng cửa của các tài sản (columns: asset symbols).
            factor_matrix: Ma trận phơi nhiễm nhân tố [N_assets x K_factors] (e.g. Market Beta, Rates, DXY).
            growth_indicator: Điểm gia tốc tăng trưởng kinh tế [-2.0, 2.0].
            inflation_indicator: Điểm gia tốc lạm phát [-2.0, 2.0].
            tactical_alpha_signals: Tín hiệu alpha chiến thuật từ Congress Alpha (BUY: >0, SELL: <0).
            alpha_tactical_weight: Tỷ lệ pha trộn tín hiệu chiến thuật [0.0, 1.0].
            factor_leakage_tol: Ngưỡng dung sai rò rỉ rủi ro hệ thống.
        """
        assets = list(price_history_df.columns)
        n_assets = len(assets)
        if n_assets == 0:
            raise ValueError("Bảng dữ liệu giá không có tài sản nào.")

        if factor_matrix.shape[0] != n_assets:
            raise ValueError(
                f"Ma trận factor có {factor_matrix.shape[0]} hàng, nhưng có {n_assets} tài sản."
            )

        # 1. Tính toán lợi suất log sinh nhật
        returns_df = np.log(price_history_df / price_history_df.shift(1)).dropna()

        # 2. MIT AMH: Kiểm định Lo-MacKinlay Variance Ratio trên tài sản chủ đạo (hoặc trung bình)
        first_asset_prices = price_history_df.iloc[:, 0].values
        vr_audit = MITMatrixCompensator.lo_mackinlay_variance_ratio(first_asset_prices, q=5)

        # 3. Đồng bộ hóa với Quyết định Định lượng FED (nếu được cung cấp)
        fed_multiplier = 1.0
        fed_summary = None
        effective_growth = growth_indicator
        effective_inflation = inflation_indicator

        if fed_assessment:
            effective_growth = fed_assessment.get("derived_macro_growth_score", growth_indicator)
            effective_inflation = fed_assessment.get("derived_macro_inflation_score", inflation_indicator)
            fed_multiplier = float(fed_assessment.get("final_fed_liquidity_multiplier", 1.0))
            fed_summary = {
                "stance": getattr(fed_assessment.get("taylor_rule"), "monetary_stance", "N/A"),
                "policy_gap": getattr(fed_assessment.get("taylor_rule"), "policy_gap", 0.0),
                "yield_curve": getattr(fed_assessment.get("yield_curve"), "yield_curve_regime", "N/A"),
                "is_inverted": getattr(fed_assessment.get("yield_curve"), "is_inverted", False),
                "net_liquidity_mode": getattr(fed_assessment.get("net_liquidity"), "qe_qt_mode", "NEUTRAL"),
                "liquidity_multiplier": fed_multiplier,
            }

        # 4. Ray Dalio: Phân loại 4 Macro Quadrants
        macro_state = RayDalioMacroEngine.classify_macro_quadrant(
            growth_indicator=effective_growth,
            inflation_indicator=effective_inflation
        )

        # 5. Ray Dalio: Holy Grail Risk Parity (Equal Risk Contribution)
        risk_parity = RayDalioMacroEngine.calculate_holy_grail_risk_parity(
            returns_df=returns_df,
            quadrant_tilt=macro_state.recommended_tilts
        )
        base_rp_weights = np.array([risk_parity.weights[a] for a in assets])

        # 6. Pha trộn Tactical Alpha (nếu có từ Congress Alpha)
        if tactical_alpha_signals:
            tactical_vec = np.zeros(n_assets)
            for i, a in enumerate(assets):
                tactical_vec[i] = tactical_alpha_signals.get(a, 0.0)

            # Chuẩn hóa vector tactical
            norm = np.sum(np.abs(tactical_vec))
            if norm > 0:
                tactical_vec = tactical_vec / norm

            # Trộn trọng số: (1 - w_tactical) * RiskParity + w_tactical * TacticalAlpha
            w_raw = (1.0 - alpha_tactical_weight) * base_rp_weights + alpha_tactical_weight * tactical_vec
            # Chuẩn hóa tổng trọng số
            sum_w = np.sum(np.abs(w_raw))
            if sum_w > 0:
                w_raw = w_raw / sum_w
        else:
            w_raw = base_rp_weights

        # 7. Thuật toán bù & Chiếu trực giao MIT Strang Nullspace
        hedge_audit = MITMatrixCompensator.calculate_factor_compensation(
            raw_weights=w_raw,
            factor_matrix=factor_matrix,
            tolerance=factor_leakage_tol
        )
        w_neutralized = hedge_audit.neutralized_weights
        w_compensating = hedge_audit.compensating_hedge_weights

        # 8. Peter Kempthorne Givens Rotation: Tìm và de-risk cặp tương quan cao nhất
        givens_hedges: Dict[str, Dict[str, float]] = {}
        corr_matrix = returns_df.corr().values
        if n_assets >= 2:
            # Tìm cặp có tương quan tuyệt đối lớn nhất
            mask = np.triu(np.ones((n_assets, n_assets), dtype=bool), k=1)
            corr_masked = np.where(mask, np.abs(corr_matrix), -1.0)
            max_idx = np.unravel_index(np.argmax(corr_masked), corr_masked.shape)
            i, j = max_idx[0], max_idx[1]
            asset_i, asset_j = assets[i], assets[j]

            theta, beta, G, rot_cov = MITMatrixCompensator.givens_covariance_diagonalization(
                returns_df[asset_i].values,
                returns_df[asset_j].values
            )
            givens_hedges[f"{asset_i}_{asset_j}"] = {
                "rotation_angle_deg": round(float(np.degrees(theta)), 2),
                "optimal_hedge_ratio_beta": round(beta, 4),
                "residual_cross_covariance": round(float(rot_cov[0, 1]), 8)
            }

        # 9. Đánh giá trạng thái và thẩm định
        if not hedge_audit.is_strictly_orthogonal:
            status = "REJECTED_FACTOR_LEAKAGE"
        elif vr_audit.market_regime == "RANDOM_WALK":
            status = "CAUTION_RANDOM_WALK"
        else:
            status = "AUDITED_AND_APPROVED"

        raw_weights_dict = {assets[i]: round(float(w_raw[i]), 6) for i in range(n_assets)}
        comp_weights_dict = {assets[i]: round(float(w_compensating[i]), 6) for i in range(n_assets)}
        neutral_weights_dict = {assets[i]: round(float(w_neutralized[i]), 6) for i in range(n_assets)}

        return UnifiedAllocationVerdict(
            assets=assets,
            raw_weights=raw_weights_dict,
            compensating_hedge_weights=comp_weights_dict,
            final_neutralized_weights=neutral_weights_dict,
            factor_leakage_max=hedge_audit.max_residual_leakage,
            is_factor_neutral=hedge_audit.is_strictly_orthogonal,
            macro_regime=macro_state,
            risk_parity_metrics=risk_parity,
            primary_variance_ratio=vr_audit,
            givens_pair_hedges=givens_hedges,
            fed_liquidity_multiplier=round(fed_multiplier, 3),
            fed_policy_summary=fed_summary,
            verdict_status=status
        )

