"""
Binh Chủng 1: TRINH SÁT & VIỄN THÁM (RECONNAISSANCE & SIGNALS INTELLIGENCE)
Vũ khí: Market Microstructure, Order Flow Imbalance, Tick Volume Spikes, Alpha #6, Alpha #101.
Nhiệm vụ: Đi trước tiền trạm, thám thính vết chân của các quỹ tạo lập (Market Makers),
phát hiện sớm sự tích lũy/phân phối ngầm trước khi giá bùng nổ.
"""

from typing import Dict, Any
import numpy as np
import pandas as pd


class ReconnaissanceUnit:
    """Binh chủng Trinh sát: Phát hiện tín hiệu vi mô thị trường."""

    NAME = "RECON_INTEL_UNIT"

    @classmethod
    def scan_market(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Quét dữ liệu vi mô:
        - Alpha #6: Nghịch đảo tương quan Open - Volume (phát hiện áp lực ngầm).
        - Alpha #101: Tỷ số thân nến trên biên độ nến.
        - Volume Delta: Lực mua/bán chủ động ước lượng.
        """
        if len(df) < 10:
            return {"signal": 0.0, "confidence": 0.0, "status": "SCOUTING"}

        close = df["close"]
        open_p = df["open"] if "open" in df else close
        high = df["high"] if "high" in df else close * 1.001
        low = df["low"] if "low" in df else close * 0.999
        vol = df["volume"] if "volume" in df else df.get("tick_volume", pd.Series(1000, index=df.index))

        # Alpha #6: -1 * corr(open, volume, 10)
        corr_ov = open_p.rolling(10, min_periods=3).corr(vol).fillna(0.0).iloc[-1]
        alpha_6_val = -1.0 * float(corr_ov)

        # Alpha #101: (close - open) / (high - low + eps)
        alpha_101_val = float(((close - open_p) / ((high - low) + 1e-6)).iloc[-1])

        # Volume Flow Momentum
        vol_delta = float(vol.pct_change().fillna(0.0).iloc[-1])
        price_delta = float(close.pct_change().fillna(0.0).iloc[-1])
        flow_imbalance = np.sign(price_delta) * min(1.0, abs(vol_delta))

        # Combined Recon Score [-1.0, +1.0]
        recon_score = np.clip(0.4 * alpha_101_val + 0.3 * alpha_6_val + 0.3 * flow_imbalance, -1.0, 1.0)
        confidence = abs(recon_score)

        return {
            "unit": cls.NAME,
            "recon_score": round(float(recon_score), 4),
            "confidence": round(float(confidence), 4),
            "intel": {
                "alpha_6_stealth": round(alpha_6_val, 4),
                "alpha_101_pressure": round(alpha_101_val, 4),
                "flow_imbalance": round(flow_imbalance, 4)
            },
            "status": "ENEMY_SPOTTED_LONG" if recon_score > 0.2 else ("ENEMY_SPOTTED_SHORT" if recon_score < -0.2 else "RECON_CLEAR")
        }
