"""
Bộ Lọc Học Máy Thứ Cấp Meta-Labeling & Định Cỡ Vị Thế Fractional Kelly.
Dựa trên Marcos López de Prado, 'Advances in Financial Machine Learning' (Chương 3 & 10)
và J.L. Kelly Jr. (1956) 'A New Interpretation of Information Rate'.

Nguyên Lý Vận Hành:
1. Mô hình cấp 1 (Primary Model): Chỉ quyết định phương hướng (BUY hoặc SELL).
2. Bộ lọc cấp 2 (Meta-Labeling): Đánh giá xác suất thành công thực tế P(Win) của lệnh
   trong bối cảnh biến động, thanh khoản và regime thị trường hiện tại.
3. Nếu P(Win) < 0.52 -> Loại bỏ lệnh hoàn toàn (False Positive Gatekeeper).
4. Nếu P(Win) >= 0.52 -> Điều chỉnh quy mô lot động theo công thức Fractional Kelly.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.stats import norm



@dataclass(frozen=True)
class MetaLabelingVerdict:
    """Kết quả thẩm định của bộ lọc Meta-Labeling và định cỡ Kelly."""
    primary_action: str             # 'BUY', 'SELL', 'HOLD'
    win_probability: float          # P(Win) in [0.0, 1.0]
    is_approved: bool               # True nếu P(Win) >= min_win_prob
    kelly_fraction: float           # Hệ số Kelly lý thuyết
    fractional_kelly_multiplier: float  # Hệ số nhân áp dụng lên base_lots [0.0, 2.0]
    recommended_lots: float         # Số lot cuối cùng
    rejection_reason: Optional[str] = None


class MetaLabelingFilter:
    """
    Bộ lọc thứ cấp và định cỡ vị thế toán học Fractional Kelly.
    """

    @staticmethod
    def compute_fractional_kelly(
        win_prob: float,
        payout_ratio_b: float = 1.5,    # Tỷ lệ Win/Loss payoff (TP / SL, ví dụ TP 1.5R, SL 1.0R -> b = 1.5)
        kelly_fraction_lambda: float = 0.50, # Half-Kelly (50% full Kelly để kiểm soát biến động)
        max_multiplier: float = 2.0
    ) -> Tuple[float, float]:
        """
        Tính toán quy mô cược tối ưu theo công thức Kelly:
        f* = (p * b - (1 - p)) / b
        f_fractional = lambda * f*
        """
        p = float(np.clip(win_prob, 0.0, 1.0))
        q = 1.0 - p
        b = max(payout_ratio_b, 0.1)

        # Full Kelly
        full_kelly = (p * b - q) / b

        if full_kelly <= 0:
            return 0.0, 0.0

        fractional_kelly = full_kelly * kelly_fraction_lambda
        multiplier = float(np.clip(fractional_kelly / (0.5 * kelly_fraction_lambda), 0.1, max_multiplier))

        return float(round(full_kelly, 4)), float(round(multiplier, 3))

    @classmethod
    def evaluate_conviction_and_size(
        cls,
        primary_action: str,
        signal_strength: float,
        market_regime: str,
        variance_ratio: float,
        volatility_gk: float,
        fed_liquidity_multiplier: float = 1.0,
        base_lots: float = 5.0,
        min_win_prob_threshold: float = 0.52
    ) -> MetaLabelingVerdict:
        """
        Thẩm định độ tin cậy của lệnh đề xuất từ Hạ Viện và định cỡ vị thế tối ưu.
        """
        if primary_action == "HOLD":
            return MetaLabelingVerdict(
                primary_action="HOLD",
                win_probability=0.50,
                is_approved=False,
                kelly_fraction=0.0,
                fractional_kelly_multiplier=0.0,
                recommended_lots=0.0,
                rejection_reason="PRIMARY_ACTION_HOLD"
            )

        # 1. Tính toán xác suất thành công ngầm định (Meta-Model Probability Score)
        # Bắt đầu từ xác suất cân bằng 0.50
        base_prob = 0.50

        # Cường độ tín hiệu formulaic alpha (+0.00 đến +0.15)
        alpha_boost = float(np.clip(signal_strength, 0.0, 1.0)) * 0.15

        # Đánh giá chế độ thị trường từ Lo-MacKinlay Variance Ratio:
        # Nếu đang ở RANDOM_WALK, phạt nặng xác suất thắng vì thị trường đang nhiễu ngẫu nhiên
        if market_regime == "RANDOM_WALK":
            regime_adj = -0.06
        elif market_regime == "MOMENTUM_TREND":
            regime_adj = 0.05
        elif market_regime == "MEAN_REVERTING":
            regime_adj = 0.04
        else:
            regime_adj = 0.0

        # Điều chỉnh theo biến động vi cấu trúc Garman-Klass (Biến động quá cao làm tăng rủi ro chạm SL)
        if volatility_gk > 0.035: # Bão tố
            vol_adj = -0.05
        elif volatility_gk < 0.008: # Siêu trầm lắng
            vol_adj = -0.02
        else:
            vol_adj = 0.02

        # Điều chỉnh theo thanh khoản vĩ mô của Fed
        fed_adj = (fed_liquidity_multiplier - 1.0) * 0.05

        win_probability = float(base_prob + alpha_boost + regime_adj + vol_adj + fed_adj)
        win_probability = float(np.clip(win_probability, 0.30, 0.85))

        # 2. Kiểm tra ngưỡng phê chuẩn
        is_approved = bool(win_probability >= min_win_prob_threshold)

        if not is_approved:
            return MetaLabelingVerdict(
                primary_action=primary_action,
                win_probability=round(win_probability, 4),
                is_approved=False,
                kelly_fraction=0.0,
                fractional_kelly_multiplier=0.0,
                recommended_lots=0.0,
                rejection_reason=f"WIN_PROB_{win_probability:.3f}_BELOW_THRESHOLD_{min_win_prob_threshold:.2f}"
            )

        # 3. Tính toán Fractional Kelly
        full_k, mult = cls.compute_fractional_kelly(
            win_prob=win_probability,
            payout_ratio_b=1.5,
            kelly_fraction_lambda=0.50,
            max_multiplier=2.0
        )

        recommended_lots = round(base_lots * mult, 2)

        return MetaLabelingVerdict(
            primary_action=primary_action,
            win_probability=round(win_probability, 4),
            is_approved=True,
            kelly_fraction=full_k,
            fractional_kelly_multiplier=mult,
            recommended_lots=recommended_lots,
            rejection_reason=None
        )
