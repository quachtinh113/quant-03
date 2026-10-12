"""
Chiết Xuất Chiến Lược & Thuật Toán Định Lượng Của Cục Dự Trữ Liên Bang Hoa Kỳ (FED).
Bao gồm các mô hình định lượng kinh tế học vĩ mô và thanh khoản trung ương:
1. Quy Tắc Taylor Kinh Điển & Quán Tính (John Taylor 1993; Clarida, Gali & Gertler 2000):
   i_t = rho * i_{t-1} + (1 - rho) * [r* + pi_t + 0.5(pi_t - pi*) + 0.5(y_t - y*)]
   Xác định độ lệch chính sách tiền tệ (Monetary Policy Gap) -> Diều hâu (Hawkish) vs Bồ câu (Dovish).
2. Mô Hình Đường Cong Lợi Suất Nelson-Siegel (Charles Nelson & Andrew Siegel 1987):
   y(tau) = beta_0 + beta_1 * ((1 - exp(-tau/lambda))/(tau/lambda)) + beta_2 * (...)
   Tách 3 nhân tố: Level (Mặt bằng), Slope (Độ dốc/Kỳ vọng suy thoái), Curvature (Độ cong).
   Phát hiện hiện tượng Đảo ngược Đường cong Lợi suất (Inverted Yield Curve 2Y-10Y).
3. Mô Hình Thanh Khoản Ròng FED (Fed Net Liquidity):
   Net_Liquidity = Fed_Total_Assets - Treasury_General_Account (TGA) - Reverse_Repo (RRP).
   Điều tiết hạn mức đòn bẩy và thanh khoản danh mục toàn hệ thống.
4. Chỉ Số Căng Thẳng Tài Chính St. Louis Fed (STLFSI Proxy):
   Tổng hợp độ lệch chính sách, chênh lệch kỳ hạn và biến động để sinh ra Central Bank Stress Multiplier.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


@dataclass(frozen=True)
class TaylorRuleAudit:
    """Kết quả thẩm định chính sách tiền tệ theo Quy tắc Taylor."""
    taylor_target_rate: float
    inertial_target_rate: float
    current_fed_funds_rate: float
    policy_gap: float             # current_rate - target_rate (> 0: Overtightening/Hawkish, < 0: Accommodative/Dovish)
    inflation_gap: float          # pi - pi*
    output_gap: float             # y - y*
    monetary_stance: str          # 'HAWKISH_TIGHTENING', 'DOVISH_EASING', 'NEUTRAL_BALANCED'
    recommended_leverage_cap: float


@dataclass(frozen=True)
class YieldCurveAudit:
    """Kết quả phân tích đường cong lợi suất Nelson-Siegel."""
    level_beta0: float            # Mặt bằng lãi suất dài hạn
    slope_beta1: float            # Độ dốc đường cong
    curvature_beta2: float        # Độ cong trung hạn
    spread_2y_10y: float          # Chênh lệch kỳ hạn 10Y - 2Y
    is_inverted: bool             # True nếu 10Y < 2Y (Báo hiệu nguy cơ suy thoái)
    recession_probability: float  # Ước lượng xác suất suy thoái theo hàm Probit ngầm định
    yield_curve_regime: str       # 'NORMAL_STEEP', 'FLAT', 'INVERTED_WARNING'


@dataclass(frozen=True)
class FedLiquidityAudit:
    """Đánh giá trạng thái thanh khoản ròng của Ngân Hàng Trung Ương."""
    net_liquidity_billions: float
    liquidity_momentum_pct: float
    st_louis_stress_index: float
    systemic_leverage_multiplier: float
    qe_qt_mode: str               # 'ACTIVE_QE_EXPANSION', 'ACTIVE_QT_DRAIN', 'NEUTRAL'


class TaylorRuleEngine:
    """
    Quy tắc Taylor (Taylor Rule) định lượng lãi suất mục tiêu của Cục Dự Trữ Liên Bang.
    """

    def __init__(
        self,
        r_star: float = 0.5,        # Lãi suất thực cân bằng trung tính r* (Neutral real rate)
        target_inflation: float = 2.0, # Mục tiêu lạm phát dài hạn pi* (2.0%)
        alpha_inflation: float = 0.5,
        alpha_output: float = 0.5,
        inertia_rho: float = 0.80   # Tham số quán tính điều hành lãi suất (Interest rate smoothing)
    ):
        self.r_star = r_star
        self.target_inflation = target_inflation
        self.alpha_inflation = alpha_inflation
        self.alpha_output = alpha_output
        self.inertia_rho = inertia_rho

    def evaluate_policy_stance(
        self,
        current_inflation: float,
        output_gap: float,
        current_fed_funds_rate: float,
        previous_fed_funds_rate: Optional[float] = None
    ) -> TaylorRuleAudit:
        """
        Tính toán lãi suất mục tiêu Taylor và đánh giá trạng thái diều hâu / bồ câu của Fed.
        """
        inf_gap = current_inflation - self.target_inflation

        # 1. Công thức Taylor 1993: i = r* + pi + 0.5(pi - pi*) + 0.5(y - y*)
        taylor_raw = (
            self.r_star
            + current_inflation
            + self.alpha_inflation * inf_gap
            + self.alpha_output * output_gap
        )

        # 2. Quy tắc Taylor có quán tính (Inertial Taylor Rule)
        prev_rate = previous_fed_funds_rate if previous_fed_funds_rate is not None else current_fed_funds_rate
        inertial_target = self.inertia_rho * prev_rate + (1.0 - self.inertia_rho) * taylor_raw

        # 3. Độ lệch chính sách: Policy Gap = Lãi suất thực tế - Lãi suất Taylor
        policy_gap = current_fed_funds_rate - inertial_target

        if policy_gap > 0.50:
            stance = "HAWKISH_TIGHTENING"
            leverage_cap = 1.0  # Giảm đòn bẩy khi Fed siết chặt quá mức
        elif policy_gap < -0.50:
            stance = "DOVISH_EASING"
            leverage_cap = 2.5  # Mở rộng đòn bẩy khi Fed nới lỏng tiền tệ
        else:
            stance = "NEUTRAL_BALANCED"
            leverage_cap = 1.8

        return TaylorRuleAudit(
            taylor_target_rate=round(taylor_raw, 3),
            inertial_target_rate=round(inertial_target, 3),
            current_fed_funds_rate=round(current_fed_funds_rate, 3),
            policy_gap=round(policy_gap, 3),
            inflation_gap=round(inf_gap, 3),
            output_gap=round(output_gap, 3),
            monetary_stance=stance,
            recommended_leverage_cap=leverage_cap
        )


class NelsonSiegelYieldCurve:
    """
    Mô hình Đường Cong Lợi Suất Nelson-Siegel (1987) phân rã cấu trúc kỳ hạn lãi suất Fed.
    """

    @staticmethod
    def nelson_siegel_func(tau: np.ndarray, beta0: float, beta1: float, beta2: float, lambda_param: float = 1.37) -> np.ndarray:
        """
        Hàm định giá Nelson-Siegel giải tích cho kỳ hạn tau:
        y(tau) = beta0 + beta1 * ((1 - exp(-tau/lambda))/(tau/lambda)) + beta2 * (((1 - exp(-tau/lambda))/(tau/lambda)) - exp(-tau/lambda))
        """
        tau_safe = np.maximum(tau, 1e-6)
        term1 = (1.0 - np.exp(-tau_safe / lambda_param)) / (tau_safe / lambda_param)
        term2 = term1 - np.exp(-tau_safe / lambda_param)
        return beta0 + beta1 * term1 + beta2 * term2

    @classmethod
    def fit_yield_curve(
        cls,
        maturities: np.ndarray,
        yields: np.ndarray
    ) -> YieldCurveAudit:
        """
        Khớp dữ liệu đường cong lợi suất Kho bạc Mỹ (Treasuries) qua các kỳ hạn:
        maturities (năm): [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        yields (%): [5.25, 5.10, 4.80, 4.20, 3.90, 4.05, 4.30]
        """
        mat = np.asarray(maturities, dtype=float)
        y = np.asarray(yields, dtype=float)

        # Khởi tạo tham số xấp xỉ
        p0 = [float(y[-1]), float(y[0] - y[-1]), 0.0]
        try:
            popt, _ = curve_fit(
                lambda t, b0, b1, b2: cls.nelson_siegel_func(t, b0, b1, b2, lambda_param=1.37),
                mat,
                y,
                p0=p0,
                maxfev=5000
            )
            beta0, beta1, beta2 = popt[0], popt[1], popt[2]
        except Exception:
            # Ước lượng giải tích trực tiếp nếu hồi quy phi tuyến không hội tụ
            beta0 = float(y[-1])
            beta1 = float(y[0] - y[-1])
            beta2 = 0.0

        # Tính toán lợi suất 2Y và 10Y mô hình hóa
        y_2y = float(cls.nelson_siegel_func(np.array([2.0]), beta0, beta1, beta2)[0])
        y_10y = float(cls.nelson_siegel_func(np.array([10.0]), beta0, beta1, beta2)[0])
        spread_2_10 = y_10y - y_2y
        is_inverted = bool(spread_2_10 < 0.0)

        # Tính xác suất suy thoái theo mô hình Probit của NY Fed:
        # P(Recession) = Phi(-0.5 - 1.5 * spread_2_10)
        z = -0.5 - 1.5 * spread_2_10
        # Hàm sigmoid xấp xỉ phi hàm phân phối chuẩn
        recession_prob = float(1.0 / (1.0 + np.exp(-z)))

        if is_inverted:
            regime = "INVERTED_WARNING"
        elif spread_2_10 < 0.40:
            regime = "FLAT"
        else:
            regime = "NORMAL_STEEP"

        return YieldCurveAudit(
            level_beta0=round(float(beta0), 3),
            slope_beta1=round(float(beta1), 3),
            curvature_beta2=round(float(beta2), 3),
            spread_2y_10y=round(spread_2_10, 3),
            is_inverted=is_inverted,
            recession_probability=round(recession_prob, 3),
            yield_curve_regime=regime
        )


class FedNetLiquidityEngine:
    """
    Mô hình Thanh Khoản Ròng của Fed (Fed Net Liquidity Model).
    Net Liquidity = Fed Total Assets - Treasury General Account (TGA) - Reverse Repo (RRP).
    """

    @staticmethod
    def compute_net_liquidity(
        fed_assets_b: float,
        tga_balance_b: float,
        rrp_balance_b: float,
        prev_net_liquidity_b: Optional[float] = None,
        market_vix: float = 16.0
    ) -> FedLiquidityAudit:
        """
        Tính toán thanh khoản thực và hệ số đòn bẩy trung ương.
        Đơn vị: Tỷ USD (Billions).
        """
        net_liq = fed_assets_b - tga_balance_b - rrp_balance_b

        # Tính đà tăng trưởng thanh khoản (Liquidity Momentum)
        if prev_net_liquidity_b is not None and prev_net_liquidity_b > 0:
            liq_momentum = ((net_liq - prev_net_liquidity_b) / prev_net_liquidity_b) * 100.0
        else:
            liq_momentum = 0.0

        # Chỉ số St. Louis Fed Stress Index (Proxy kết hợp biến động và đà thanh khoản)
        # Giá trị bình thường quanh 0.0, stress cao > 1.0, khủng hoảng > 2.0
        stress_index = (market_vix - 18.0) * 0.10 - (liq_momentum * 0.20)
        stress_index = float(np.clip(stress_index, -2.5, 4.0))

        # Phân loại trạng thái QE / QT
        if liq_momentum > 1.5:
            mode = "ACTIVE_QE_EXPANSION"
            base_mult = 1.30
        elif liq_momentum < -1.5:
            mode = "ACTIVE_QT_DRAIN"
            base_mult = 0.65
        else:
            mode = "NEUTRAL"
            base_mult = 1.0

        # Điều chỉnh đòn bẩy theo Stress Index
        leverage_multiplier = float(np.clip(base_mult * np.exp(-0.3 * max(0.0, stress_index)), 0.30, 2.0))

        return FedLiquidityAudit(
            net_liquidity_billions=round(net_liq, 2),
            liquidity_momentum_pct=round(liq_momentum, 2),
            st_louis_stress_index=round(stress_index, 3),
            systemic_leverage_multiplier=round(leverage_multiplier, 3),
            qe_qt_mode=mode
        )


class CentralBankQuantitativeMaster:
    """
    Bộ Chỉ Huy Tổng Hợp Định Lượng FED:
    Hợp nhất Quy tắc Taylor + Đường cong Lợi suất Nelson-Siegel + Thanh khoản Ròng SOMA.
    """

    def __init__(self):
        self.taylor_engine = TaylorRuleEngine()
        self.yield_curve_engine = NelsonSiegelYieldCurve()
        self.liquidity_engine = FedNetLiquidityEngine()

    def generate_fed_macro_assessment(
        self,
        current_inflation: float,
        output_gap: float,
        current_fed_funds_rate: float,
        maturities: np.ndarray,
        yields: np.ndarray,
        fed_assets_b: float = 7500.0,
        tga_balance_b: float = 750.0,
        rrp_balance_b: float = 400.0,
        prev_net_liquidity_b: Optional[float] = 6300.0,
        market_vix: float = 16.0
    ) -> Dict[str, Any]:
        """
        Xuất bản Báo Cáo Quyết Định Tiền Tệ Định Lượng Toàn Diện của FED.
        """
        # 1. Thẩm định Quy tắc Taylor
        taylor_audit = self.taylor_engine.evaluate_policy_stance(
            current_inflation=current_inflation,
            output_gap=output_gap,
            current_fed_funds_rate=current_fed_funds_rate
        )

        # 2. Thẩm định Đường cong Nelson-Siegel
        curve_audit = self.yield_curve_engine.fit_yield_curve(
            maturities=maturities,
            yields=yields
        )

        # 3. Thẩm định Thanh khoản Ròng
        liq_audit = self.liquidity_engine.compute_net_liquidity(
            fed_assets_b=fed_assets_b,
            tga_balance_b=tga_balance_b,
            rrp_balance_b=rrp_balance_b,
            prev_net_liquidity_b=prev_net_liquidity_b,
            market_vix=market_vix
        )

        # Tổng hợp khuyến nghị vĩ mô cho Ray Dalio 4 Quadrants
        # Nếu Fed thắt chặt mạnh + đường cong đảo ngược -> Tăng trưởng Giảm mạnh
        growth_indicator = float(output_gap - 0.5 * max(0.0, taylor_audit.policy_gap) - (1.5 if curve_audit.is_inverted else 0.0))
        inflation_indicator = float(taylor_audit.inflation_gap)

        return {
            "taylor_rule": taylor_audit,
            "yield_curve": curve_audit,
            "net_liquidity": liq_audit,
            "derived_macro_growth_score": round(growth_indicator, 2),
            "derived_macro_inflation_score": round(inflation_indicator, 2),
            "final_fed_liquidity_multiplier": liq_audit.systemic_leverage_multiplier,
            "is_emergency_tightening": bool(taylor_audit.policy_gap > 1.0 or curve_audit.is_inverted or liq_audit.qe_qt_mode == "ACTIVE_QT_DRAIN")
        }
