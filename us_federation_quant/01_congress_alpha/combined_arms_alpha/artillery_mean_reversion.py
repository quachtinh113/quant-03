"""
Binh Chủng 3: PHÁO BINH TẦM XA (ARTILLERY & SUPPRESSION FIRE)
Vũ khí: Bollinger Z-Score, Ornstein-Uhlenbeck Mean-Reversion, Cointegration Spread.
Nhiệm vụ: Dập hỏa lực chế áp từ xa khi giá bay quá xa khỏi giá trị cân bằng thống kê (Outlier).
Kéo giá quay trở lại tâm dao động (Mean Reversion) và càn quét lợi nhuận liên tục khi thị trường đi ngang (Chop/Sideway).
"""

from typing import Dict, Any
import numpy as np
import pandas as pd


class ArtilleryMeanReversionUnit:
    """Binh chủng Pháo binh: Bắn chặn các vị trí giá bị kéo dãn quá mức."""

    NAME = "ARTILLERY_FIRE_UNIT"

    @classmethod
    def fire_barrage(cls, df: pd.DataFrame, window: int = 20) -> Dict[str, Any]:
        """
        Tính toán tọa độ pháo kích:
        - Z-Score của giá so với SMA(window): z = (Price - Mean) / Std
        - Khi |z| > 2.0: Pháo binh nã đạn ngược chiều để ép giá quay về điểm cân bằng.
        - Khi |z| < 0.5: Pháo binh ngưng bắn (đã đạt mục tiêu chế áp).
        """
        if len(df) < window:
            return {"barrage_power": 0.0, "firing": False, "target": "NO_TARGET"}

        close = df["close"]
        sma = close.rolling(window, min_periods=window).mean().iloc[-1]
        std = close.rolling(window, min_periods=window).std().iloc[-1] + 1e-8
        current_price = close.iloc[-1]

        z_score = float((current_price - sma) / std)

        # Pháo binh bắn ngược hướng kéo dãn:
        # Nếu giá vọt lên quá cao (z > 2.0) -> Bắn đạn BÁN (SHORT)
        # Nếu giá rơi quá sâu (z < -2.0) -> Bắn đạn MUA (LONG)
        firing = abs(z_score) >= 1.75
        
        if z_score >= 1.75:
            # Quá mua -> Bắn ép giá xuống
            barrage_power = -1.0 * min(1.0, (z_score - 1.0) / 1.5)
            target = "SUPPRESS_OVERBOUGHT_SHORT"
        elif z_score <= -1.75:
            # Quá bán -> Bắn nâng giá lên
            barrage_power = +1.0 * min(1.0, (-z_score - 1.0) / 1.5)
            target = "SUPPORT_OVERSOLD_LONG"
        else:
            barrage_power = 0.0
            target = "EQUILIBRIUM_HOLD"

        return {
            "unit": cls.NAME,
            "barrage_power": round(float(barrage_power), 4),
            "z_score": round(z_score, 4),
            "firing": firing,
            "target": target
        }
