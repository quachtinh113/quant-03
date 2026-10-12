"""
Market Impact and Slippage Estimation Model.
Implements the Square-Root Law of Market Impact and Kyle's Lambda formulation:
Calculates temporary and permanent market impact (in basis points and dollar terms)
as a function of order size relative to Average Daily Volume (ADV) and market volatility.
"""

import math
from typing import Dict, Any


class SlippageImpactModel:
    """
    Quantitative Market Impact and Execution Slippage Estimator.
    """

    #: Trần TUYỆT ĐỐI theo CLAUDE.md §2① — Giới hạn thanh khoản: khối lượng một lệnh
    #: không được vượt 10% khối lượng giao dịch trung bình ngày. Không mã nào được phép
    #: đặt `adv_participation_cap` cao hơn con số này.
    DIRECTIVE_ADV_CEILING: float = 0.10

    def __init__(
        self,
        temp_coefficient: float = 0.5,    # Temporary impact scaling constant
        perm_coefficient: float = 0.1,    # Permanent impact scaling constant
        adv_participation_cap: float = 0.05  # Mặc định 5% — xem ghi chú bên dưới
    ):
        """
        :param adv_participation_cap: trần tỉ lệ tham gia thanh khoản.

            Mặc định **5%**, tức chặt hơn trần 10% mà CLAUDE.md §2① cho phép. Đây là lựa
            chọn có chủ đích: trần quy định là mức KHÔNG ĐƯỢC VƯỢT, không phải mức nên
            dùng. Tác động giá tăng theo căn bậc hai của tỉ lệ tham gia, nên khoảng 5–10%
            là vùng chi phí trượt giá leo nhanh nhất.

            Giá trị vượt `DIRECTIVE_ADV_CEILING` bị **từ chối ở cấp hàm khởi tạo**. Trước
            ngày 26/09/2026 tham số này hoàn toàn tự do, nên bất kỳ mã gọi nào cũng có thể
            đặt 0.50 và lặng lẽ vượt trần định chế.

        :raises ValueError: khi trần vượt mức quy định hoặc không nằm trong (0, 1].
        """
        if not (0.0 < adv_participation_cap <= self.DIRECTIVE_ADV_CEILING):
            raise ValueError(
                f"adv_participation_cap phai nam trong (0, {self.DIRECTIVE_ADV_CEILING}] "
                f"theo CLAUDE.md §2① (Gioi han thanh khoan ADV 10%), "
                f"nhan duoc {adv_participation_cap}."
            )
        self.temp_coefficient = temp_coefficient
        self.perm_coefficient = perm_coefficient
        self.adv_participation_cap = adv_participation_cap

    def estimate_impact(
        self,
        order_lots: float,
        mid_price: float,
        daily_adv_lots: float = 10000.0,
        volatility_sigma: float = 0.015,
        execution_window_fraction: float = 0.1  # Fraction of trading day (e.g. 1 hour of 10h = 0.1)
    ) -> Dict[str, Any]:
        """
        Estimates temporary, permanent, and total slippage impact.

        :param order_lots: Size of the order / slice in lots
        :param mid_price: Current market mid-price
        :param daily_adv_lots: Average Daily Volume in lots
        :param volatility_sigma: Daily volatility sigma
        :param execution_window_fraction: Duration tau of execution as fraction of full trading day
        :return: Comprehensive dictionary of estimated impact metrics
        """
        if order_lots <= 0:
            return {
                "order_lots": 0.0,
                "temp_impact_bps": 0.0,
                "perm_impact_bps": 0.0,
                "total_impact_bps": 0.0,
                "expected_slippage_price": 0.0,
                "total_slippage_cost": 0.0,
                "participation_rate": 0.0,
                "exceeds_adv_cap": False
            }

        tau = max(1e-4, execution_window_fraction)
        window_adv = daily_adv_lots * tau

        # Participation rate during the execution window
        participation_rate = order_lots / window_adv

        # Square-Root Law for Temporary Impact:
        # I_temp = eta * sigma * sqrt(order_lots / window_adv)
        temp_fraction = self.temp_coefficient * volatility_sigma * math.sqrt(participation_rate)
        temp_impact_bps = temp_fraction * 10000.0

        # Permanent Impact (linear or concave in total ADV fraction):
        # I_perm = gamma * sigma * (order_lots / daily_adv_lots)
        total_adv_fraction = order_lots / daily_adv_lots
        perm_fraction = self.perm_coefficient * volatility_sigma * math.sqrt(total_adv_fraction)
        perm_impact_bps = perm_fraction * 10000.0

        total_impact_bps = temp_impact_bps + 0.5 * perm_impact_bps

        # Expected price slippage
        slippage_price = round(mid_price * (total_impact_bps / 10000.0), 4)

        # Standard lot value (e.g. 100,000 units for standard FX/Metals lot)
        notional_value = order_lots * 100.0 * mid_price  # Typical futures/CFD multiplier
        total_slippage_cost = round(notional_value * (total_impact_bps / 10000.0), 2)

        exceeds_cap = participation_rate > self.adv_participation_cap

        return {
            "order_lots": round(order_lots, 4),
            "mid_price": mid_price,
            "participation_rate": round(participation_rate, 4),
            "temp_impact_bps": round(temp_impact_bps, 2),
            "perm_impact_bps": round(perm_impact_bps, 2),
            "total_impact_bps": round(total_impact_bps, 2),
            "expected_slippage_price": slippage_price,
            "total_slippage_cost": total_slippage_cost,
            "exceeds_adv_cap": exceeds_cap
        }
