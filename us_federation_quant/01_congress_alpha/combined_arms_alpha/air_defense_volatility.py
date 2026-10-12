"""
Binh Chủng 4: PHÒNG KHÔNG & CÔNG BINH PHÒNG THỦ (AIR DEFENSE & COMBAT DEFENSE)
Vũ khí: Garman-Klass Extreme-Value Volatility, Parkinson Estimator, Volatility Surge Radar.
Nhiệm vụ: Dựng vòm sắt đánh chặn các cuộc không kích bất ngờ từ thị trường (Tin tức CPI, FOMC, Chiến tranh).
Khi phát hiện bão biến động hoặc nguy cơ sụt giảm sâu, kích hoạt lá chắn bảo hiểm (Defensive Shield),
hạ thấp trọng số rủi ro của toàn bộ quân đoàn để chống thương vong hàng loạt.
"""

from typing import Dict, Any
import numpy as np
import pandas as pd


class AirDefenseVolatilityUnit:
    """Binh chủng Phòng không: Quét radar biến động và bảo vệ đội hình."""

    NAME = "AIR_DEFENSE_SHIELD"

    @classmethod
    def scan_airspace(cls, df: pd.DataFrame, window: int = 20) -> Dict[str, Any]:
        """
        Quét bầu trời biến động:
        - Garman-Klass Volatility: Đo lường chính xác gấp 8 lần Close-to-Close.
        - Volatility Surge Ratio: Tỷ lệ biến động ngắn hạn (5 bars) so với dài hạn (20 bars).
        - Khi Surge Ratio > 2.0: Kích hoạt tình trạng báo động ĐỎ (RED_ALERT) -> Siết chặt phòng thủ.
        """
        if len(df) < window:
            return {"shield_active": False, "defense_multiplier": 1.0, "status": "CLEAR_SKY"}

        close = df["close"]
        high = df["high"] if "high" in df else close * 1.002
        low = df["low"] if "low" in df else close * 0.998
        open_p = df["open"] if "open" in df else close

        # Garman-Klass Variance
        log_hl = np.log(high / low) ** 2
        log_co = np.log(close / open_p) ** 2
        var_gk = 0.5 * log_hl - (2.0 * np.log(2.0) - 1.0) * log_co

        gk_short = float(np.sqrt(np.maximum(1e-10, var_gk.rolling(5, min_periods=2).mean().iloc[-1] * 252)))
        gk_long = float(np.sqrt(np.maximum(1e-10, var_gk.rolling(window, min_periods=window).mean().iloc[-1] * 252)))

        surge_ratio = gk_short / max(gk_long, 1e-6)

        # Defense Multiplier: Giảm quy mô khi trời giông bão
        if surge_ratio >= 2.5:
            # Bão cực mạnh -> Phòng thủ tối đa, chỉ cho phép 20% hỏa lực mạo hiểm
            shield_active = True
            defense_multiplier = 0.20
            threat_level = "DEFCON_1_RED_ALERT"
        elif surge_ratio >= 1.6:
            # Có máy bay ném bom tới gần -> Thu hẹp đội hình, cho phép 50% hỏa lực
            shield_active = True
            defense_multiplier = 0.50
            threat_level = "DEFCON_2_YELLOW_ALERT"
        else:
            # Bầu trời quang đãng -> Cho phép toàn quân bung sức
            shield_active = False
            defense_multiplier = 1.00
            threat_level = "DEFCON_5_CLEAR_SKY"

        return {
            "unit": cls.NAME,
            "threat_level": threat_level,
            "shield_active": shield_active,
            "defense_multiplier": defense_multiplier,
            "garman_klass_vol": round(gk_short, 4),
            "surge_ratio": round(surge_ratio, 4)
        }
