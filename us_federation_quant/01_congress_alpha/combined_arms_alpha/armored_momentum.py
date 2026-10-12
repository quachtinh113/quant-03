"""
Binh Chủng 2: THIẾT GIÁP ĐỘT KÍCH (ARMORED CAVALRY / VANGUARD ASSAULT)
Vũ khí: Time-Series Momentum (TSMOM), Alpha #1, Trend Breakout, Multi-MA Velocity.
Nhiệm vụ: Lực lượng thọc sâu, công phá các mức kháng cự/hỗ trợ trọng yếu.
Cưỡi trên những con sóng lớn của thị trường để gặt hái siêu lợi nhuận (Profit Maximizer).
"""

from typing import Dict, Any
import numpy as np
import pandas as pd


class ArmoredMomentumUnit:
    """Binh chủng Thiết giáp: Đột kích theo xu hướng mạnh."""

    NAME = "ARMORED_MOMENTUM_UNIT"

    @classmethod
    def launch_assault(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Đánh giá sức mạnh hỏa lực đột kích:
        - TSMOM: Lợi nhuận tích lũy đa chu kỳ (12, 26, 50 bars).
        - Alpha #1: Xếp hạng đà tăng có trọng số độ lệch chuẩn biến động.
        - Đường trung bình động lũy thừa (EMA 9, 21, 50) xếp hàng song song (Alligator/Bull alignment).
        """
        if len(df) < 25:
            return {"firepower": 0.0, "readiness": False, "status": "REFUELING"}

        close = df["close"]
        
        # EMA Alignment
        ema_fast = close.ewm(span=9, adjust=False).mean().iloc[-1]
        ema_mid = close.ewm(span=21, adjust=False).mean().iloc[-1]
        ema_slow = close.ewm(span=50, adjust=False).mean().iloc[-1]
        current = close.iloc[-1]

        # Trend Formation Velocity
        if current > ema_fast > ema_mid > ema_slow:
            alignment = +1.0 # Đội hình tấn công mãnh liệt (Bull Blitzkrieg)
        elif current < ema_fast < ema_mid < ema_slow:
            alignment = -1.0 # Đội hình tháo chạy mãnh liệt (Bear Blitzkrieg)
        else:
            alignment = 0.0 # Bị kẹt trong bãi lầy

        # Alpha #1: rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5
        returns = close.pct_change().fillna(0.0)
        cond = np.where(returns < 0, returns.rolling(20, min_periods=1).std().fillna(0.0), close)
        power = pd.Series(cond, index=df.index) ** 2
        argmax = power.rolling(5, min_periods=1).apply(np.argmax, raw=True)
        alpha_1_series = argmax.rolling(20, min_periods=1).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1], raw=False) - 0.5
        alpha_1_val = float(alpha_1_series.fillna(0.0).iloc[-1])

        # Rate of Change (ROC)
        roc_10 = float((close.iloc[-1] - close.iloc[-10]) / close.iloc[-10]) if len(close) >= 10 else 0.0
        normalized_roc = np.tanh(roc_10 * 50.0)

        # Hỏa lực tổng hợp của Thiết Giáp
        firepower = np.clip(0.5 * alignment + 0.3 * np.sign(alpha_1_val) * abs(alpha_1_val) * 2.0 + 0.2 * normalized_roc, -1.0, 1.0)
        readiness = abs(firepower) >= 0.35

        return {
            "unit": cls.NAME,
            "firepower": round(float(firepower), 4),
            "readiness": readiness,
            "metrics": {
                "ema_alignment": alignment,
                "alpha_1_score": round(alpha_1_val, 4),
                "normalized_roc": round(float(normalized_roc), 4)
            },
            "status": "ASSAULT_CHARGE_BUY" if firepower > 0.35 else ("ASSAULT_CHARGE_SELL" if firepower < -0.35 else "HOLDING_POSITION")
        }
