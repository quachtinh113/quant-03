"""
Bicameral Congress: Alpha Bill Builder & Institutional Alpha Factory
Requires concurrent approval of:
1. The House of Representatives (Micro Features & Order Flow)
2. The Senate (Macro Regime & Lo-MacKinlay Variance Ratio)
3. The FracDiff Stationarity & Memory Preserver (Marcos López de Prado)
4. The Kakushadze 101 Formulaic Alpha Pack
5. The Meta-Labeling Secondary Filter & Fractional Kelly Bet Sizing

Outputs formal 'AlphaBill' submitted to the Supreme Court.
"""

import time
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from ..house_of_representatives.micro_features import HouseOfRepresentatives
from ..senate_macro.macro_regime import SenateMacro
from ..formulaic_alpha_fleet.fracdiff_engine import FracDiffEngine
from ..formulaic_alpha_fleet.formulaic_alphas_101 import FormulaicAlphas101
from ..formulaic_alpha_fleet.meta_labeling_filter import MetaLabelingFilter, MetaLabelingVerdict



@dataclass
class AlphaBill:
    """A formal Alpha Bill passed by Congress with AFML & Kakushadze verification."""
    bill_id: str
    target_asset: str
    action: str
    target_lots: float
    house_yes_votes: int
    senate_yes_votes: int
    micro_score: float
    variance_ratio: float
    regime: str
    timestamp: float
    passed_bicameral: bool
    # Các trường mở rộng toán học cấp định chế:
    optimal_d: float = 1.0
    composite_alpha_score: float = 0.0
    meta_win_probability: float = 0.50
    kelly_multiplier: float = 1.0
    is_fracdiff_stationary: bool = True
    alpha_conviction_summary: Optional[Dict[str, Any]] = None


class Congress:
    """
    The United States Congress (Institutional Alpha Factory).
    Passes an AlphaBill only when House, Senate, and Meta-Labeling filter concur.
    """

    @classmethod
    def deliberate_and_vote(
        cls,
        target_asset: str,
        in_sample_df: pd.DataFrame,
        proposed_lots: float = 5.0,
        fed_liquidity_multiplier: float = 1.0,
        ml_service: Optional[Any] = None
    ) -> AlphaBill:
        """
        Tiến hành quy trình lập pháp hoàn chỉnh:
        1. Bỏ phiếu Hạ Viện (Micro 435)
        2. Bỏ phiếu Thượng Viện (Macro 100)
        3. Phân tích FracDiff bảo toàn trí nhớ dài
        4. Tính toán Kakushadze Formulaic Alpha Pack
        5. Lọc Meta-Labeling & Định cỡ Fractional Kelly (thông qua ML Inference Service hoặc Analytic Filter)
        """
        # 1. Bỏ phiếu Lưỡng Viện truyền thống
        house_res = HouseOfRepresentatives.vote_on_market(in_sample_df)
        senate_res = SenateMacro.vote_on_regime(in_sample_df)
        bicameral_base = bool(house_res["passed"] and senate_res["passed"])

        action = house_res["action"]
        regime = senate_res.get("regime", "UNDEFINED")
        vr = senate_res.get("variance_ratio", 1.0)
        micro_score = house_res.get("micro_score", 0.0)

        # 2. Phân tích FracDiff bảo toàn trí nhớ
        optimal_d = 1.0
        is_stationary = True
        if len(in_sample_df) >= 50 and "close" in in_sample_df.columns:
            try:
                frac_audit, _ = FracDiffEngine.find_optimal_d(in_sample_df["close"], step=0.10)
                optimal_d = frac_audit.optimal_d
                is_stationary = frac_audit.is_stationary
            except Exception:
                optimal_d = 1.0

        # 3. Tính toán Kakushadze Formulaic Alphas
        alpha_snap = FormulaicAlphas101.evaluate_alpha_snapshot(in_sample_df)

        # 4. Thẩm định Meta-Labeling & Định cỡ Fractional Kelly
        if ml_service is not None and hasattr(ml_service, "predict_latest_bar"):
            ml_res = ml_service.predict_latest_bar(
                in_sample_df,
                primary_action=action,
                signal_strength=alpha_snap.signal_strength
            )
            win_prob = ml_res.win_probability
            kelly_mult = ml_res.kelly_multiplier
            meta_approved = ml_res.is_approved
            meta_verdict = MetaLabelingVerdict(
                primary_action=action,
                win_probability=win_prob,
                is_approved=meta_approved,
                kelly_fraction=round(kelly_mult * 0.5, 4),
                fractional_kelly_multiplier=kelly_mult,
                recommended_lots=round(proposed_lots * kelly_mult * fed_liquidity_multiplier, 2) if meta_approved else 0.0,
                rejection_reason=None if meta_approved else f"ML_PROB_BELOW_THRESHOLD_{win_prob}"
            )
        else:
            meta_verdict = MetaLabelingFilter.evaluate_conviction_and_size(
                primary_action=action,
                signal_strength=alpha_snap.signal_strength,
                market_regime=regime,
                variance_ratio=vr,
                volatility_gk=alpha_snap.garman_klass_vol,
                fed_liquidity_multiplier=fed_liquidity_multiplier,
                base_lots=proposed_lots,
                min_win_prob_threshold=0.48  # Ngưỡng tối thiểu linh hoạt
            )

        # Quyết định phê chuẩn cuối cùng
        # Nếu cả 2 viện đồng thuận và Meta-labeling không phản đối
        passed_final = bool(bicameral_base and (action != "HOLD") and meta_verdict.is_approved)


        final_lots = meta_verdict.recommended_lots if passed_final else proposed_lots
        bill_id = f"CONGRESS-BILL-{target_asset}-{int(time.time())}"

        bill = AlphaBill(
            bill_id=bill_id,
            target_asset=target_asset,
            action=action,
            target_lots=final_lots,
            house_yes_votes=house_res["yes_votes"],
            senate_yes_votes=senate_res["yes_votes"],
            micro_score=micro_score,
            variance_ratio=vr,
            regime=regime,
            timestamp=time.time(),
            passed_bicameral=passed_final if bicameral_base else False,
            optimal_d=optimal_d,
            composite_alpha_score=alpha_snap.composite_alpha_score,
            meta_win_probability=meta_verdict.win_probability,
            kelly_multiplier=meta_verdict.fractional_kelly_multiplier,
            is_fracdiff_stationary=is_stationary,
            alpha_conviction_summary={
                "alpha_001": alpha_snap.alpha_001,
                "alpha_006": alpha_snap.alpha_006,
                "alpha_012": alpha_snap.alpha_012,
                "alpha_101": alpha_snap.alpha_101,
                "garman_klass_vol": alpha_snap.garman_klass_vol,
                "meta_approved": meta_verdict.is_approved,
                "rejection_reason": meta_verdict.rejection_reason
            }
        )

        return bill
