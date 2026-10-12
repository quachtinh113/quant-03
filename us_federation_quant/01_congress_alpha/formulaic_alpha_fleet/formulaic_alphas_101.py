"""
Hạm Đội Formulaic Alphas 101 & Các Bộ Ước Lượng Vi Cấu Trúc.
Dựa trên:
- Zura Kakushadze (101 Formulaic Alphas, 2016)
- Stefan Jansen (Machine Learning for Algorithmic Trading)
- Garman & Klass (1980) Extreme-Value Volatility Estimators

Cung cấp các công thức alpha toán học phi tương quan nhằm mở rộng độ phủ (Breadth)
và tối đa hóa Information Ratio (IR = IC * sqrt(Breadth)).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FormulaicAlphaSnapshot:
    """Ảnh chụp giá trị các công thức Alpha Kakushadze tại thanh nến hiện tại."""
    alpha_001: float
    alpha_006: float
    alpha_012: float
    alpha_054: float
    alpha_101: float
    garman_klass_vol: float
    parkinson_vol: float
    composite_alpha_score: float  # Điểm tổng hợp [-1.0, 1.0] (BUY: >0, SELL: <0)
    signal_strength: float        # Cường độ tín hiệu [0.0, 1.0]


class FormulaicAlphas101:
    """
    Thư viện tính toán các công thức Alpha toán học kinh điển của WorldQuant & Kakushadze.
    """

    # ------------------------------------------------------------------ Toán Tử Chuỗi Thời Gian
    @staticmethod
    def ts_delay(series: pd.Series, d: int) -> pd.Series:
        return series.shift(d)

    @staticmethod
    def ts_delta(series: pd.Series, d: int) -> pd.Series:
        return series.diff(d)

    @staticmethod
    def ts_rank(series: pd.Series, d: int) -> pd.Series:
        return series.rolling(d).apply(lambda s: float(pd.Series(s).rank(pct=True).iloc[-1]), raw=False)

    @staticmethod
    def ts_corr(s1: pd.Series, s2: pd.Series, d: int) -> pd.Series:
        return s1.rolling(d).corr(s2)

    @staticmethod
    def ts_std(series: pd.Series, d: int) -> pd.Series:
        return series.rolling(d).std()

    # ------------------------------------------------------------------ Công Thức Alphas Kakushadze
    @classmethod
    def alpha_001(cls, df: pd.DataFrame) -> pd.Series:
        """
        Alpha #1: rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5
        Phát hiện phân kỳ giữa xung lượng giá và mức độ biến động trong pha giảm.
        """
        returns = df["close"].pct_change()
        std20 = returns.rolling(20).std().fillna(0.0)
        cond = np.where(returns < 0, std20, df["close"])
        power = pd.Series(cond, index=df.index) ** 2
        argmax = power.rolling(5).apply(lambda s: float(np.argmax(s)), raw=True)
        ranked = argmax.rolling(20).apply(lambda s: float(pd.Series(s).rank(pct=True).iloc[-1]), raw=False)
        return ranked - 0.5

    @classmethod
    def alpha_006(cls, df: pd.DataFrame) -> pd.Series:
        """
        Alpha #6: -1.0 * correlation(open, volume, 10)
        Tương quan nghịch đảo giữa giá mở cửa và khối lượng: Khối lượng tăng ở giá mở cửa thấp báo hiệu đáy ngắn hạn.
        """
        vol = df["volume"] if "volume" in df else df.get("tick_volume", pd.Series(1.0, index=df.index))
        corr = df["open"].rolling(10).corr(vol)
        return -1.0 * corr.fillna(0.0)

    @classmethod
    def alpha_012(cls, df: pd.DataFrame) -> pd.Series:
        """
        Alpha #12: sign(delta(volume, 1)) * (-1.0 * delta(close, 1))
        Động lượng khối lượng gán dấu ngược hướng thay đổi giá (Phát hiện cạn kiệt thanh khoản).
        """
        vol = df["volume"] if "volume" in df else df.get("tick_volume", pd.Series(1.0, index=df.index))
        return np.sign(vol.diff(1).fillna(0.0)) * (-1.0 * df["close"].diff(1).fillna(0.0))

    @classmethod
    def alpha_054(cls, df: pd.DataFrame) -> pd.Series:
        """
        Alpha #54: (-1.0 * (low - close) * (open^5)) / ((low - high) * (close^5) + 1e-12)
        Tỷ lệ bất đối xứng phi tuyến giữa vị trí giá đóng cửa trong biên độ nến và giá mở cửa lũy thừa.
        """
        num = -1.0 * (df["low"] - df["close"]) * (df["open"] ** 5)
        denom = (df["low"] - df["high"]) * (df["close"] ** 5) + 1e-12
        ratio = num / denom
        return np.clip(ratio, -5.0, 5.0)

    @classmethod
    def alpha_101(cls, df: pd.DataFrame) -> pd.Series:
        """
        Alpha #101: (close - open) / ((high - low) + 1e-12)
        Xung lượng thân nến chuẩn hóa trên toàn bộ phạm vi dao động trong phiên.
        """
        return (df["close"] - df["open"]) / ((df["high"] - df["low"]) + 1e-12)

    # ------------------------------------------------------------------ Bộ Ước Lượng Biến Động Vi Cấu Trúc
    @staticmethod
    def calculate_garman_klass_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        Garman-Klass (1980) Volatility:
        sigma_GK^2 = 0.5 * ln(H/L)^2 - (2*ln(2) - 1) * ln(C/O)^2
        Chính xác và hiệu quả gấp 8 lần so với phương sai Close-to-Close thông thường.
        """
        log_hl = np.log(np.maximum(df["high"] / np.maximum(df["low"], 1e-12), 1.0))
        log_co = np.log(np.maximum(df["close"] / np.maximum(df["open"], 1e-12), 1e-12))

        gk_var = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
        rolling_gk = gk_var.rolling(window).mean()
        return np.sqrt(np.maximum(rolling_gk, 1e-12))

    @staticmethod
    def calculate_parkinson_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        Parkinson (1980) Extreme-Value Volatility:
        sigma_P^2 = (1 / (4 * ln(2))) * ln(H/L)^2
        Ước lượng độ biến động dựa trên giá cực trị High-Low.
        """
        log_hl = np.log(np.maximum(df["high"] / np.maximum(df["low"], 1e-12), 1.0))
        p_var = (1.0 / (4.0 * np.log(2.0))) * (log_hl ** 2)
        rolling_p = p_var.rolling(window).mean()
        return np.sqrt(np.maximum(rolling_p, 1e-12))

    # ------------------------------------------------------------------ Tổng Hợp Hạm Đội Alphas
    @classmethod
    def evaluate_alpha_snapshot(cls, df: pd.DataFrame) -> FormulaicAlphaSnapshot:
        """
        Tính toán snapshot tổng hợp toàn bộ các công thức Alpha trên nến mới nhất.
        """
        if len(df) < 25:
            # Dữ liệu quá ngắn -> Trả về snapshot trung tính
            return FormulaicAlphaSnapshot(
                alpha_001=0.0,
                alpha_006=0.0,
                alpha_012=0.0,
                alpha_054=0.0,
                alpha_101=0.0,
                garman_klass_vol=0.01,
                parkinson_vol=0.01,
                composite_alpha_score=0.0,
                signal_strength=0.0
            )

        a1_s = cls.alpha_001(df)
        a6_s = cls.alpha_006(df)
        a12_s = cls.alpha_012(df)
        a54_s = cls.alpha_054(df)
        a101_s = cls.alpha_101(df)
        gk_s = cls.calculate_garman_klass_volatility(df)
        pk_s = cls.calculate_parkinson_volatility(df)

        a1 = float(a1_s.iloc[-1]) if not np.isnan(a1_s.iloc[-1]) else 0.0
        a6 = float(a6_s.iloc[-1]) if not np.isnan(a6_s.iloc[-1]) else 0.0
        a12 = float(a12_s.iloc[-1]) if not np.isnan(a12_s.iloc[-1]) else 0.0
        a54 = float(a54_s.iloc[-1]) if not np.isnan(a54_s.iloc[-1]) else 0.0
        a101 = float(a101_s.iloc[-1]) if not np.isnan(a101_s.iloc[-1]) else 0.0
        gk = float(gk_s.iloc[-1]) if not np.isnan(gk_s.iloc[-1]) else 0.01
        pk = float(pk_s.iloc[-1]) if not np.isnan(pk_s.iloc[-1]) else 0.01

        # Chuẩn hóa các alphas thành các z-score / tanh signal
        # Tỷ trọng đóng góp của các phong cách:
        # a1 (Momentum Rank): 25%
        # a6 (Volume/Open Divergence): 20%
        # a12 (Signed Volume Exhaustion): 15%
        # a54 (Intra-bar Non-linear): 15%
        # a101 (Normalized Candle Body): 25%
        s1 = np.tanh(a1 * 4.0)
        s6 = np.tanh(a6 * 2.0)
        s12 = np.tanh(a12 * 0.5)
        s54 = np.tanh(a54 * 0.5)
        s101 = np.tanh(a101 * 2.0)

        composite = float(0.25 * s1 + 0.20 * s6 + 0.15 * s12 + 0.15 * s54 + 0.25 * s101)
        composite = float(np.clip(composite, -1.0, 1.0))
        strength = float(abs(composite))

        return FormulaicAlphaSnapshot(
            alpha_001=round(a1, 4),
            alpha_006=round(a6, 4),
            alpha_012=round(a12, 4),
            alpha_054=round(a54, 4),
            alpha_101=round(a101, 4),
            garman_klass_vol=round(gk, 5),
            parkinson_vol=round(pk, 5),
            composite_alpha_score=round(composite, 4),
            signal_strength=round(strength, 4)
        )
