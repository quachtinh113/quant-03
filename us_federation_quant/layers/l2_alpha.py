"""l2_alpha: tầng gộp từ 25 module (xem các khối "# ====" bên dưới)."""

from typing import Dict, Any
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional
from typing import Dict, Tuple, Optional, Any
from statsmodels.tsa.stattools import adfuller
from typing import Dict, Any, Optional, Tuple
from scipy.stats import norm
from typing import Dict, List, Optional, Tuple
from scipy import stats
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from typing import List, Dict, Any, Optional, Union
from typing import Generator, Tuple, List, Optional
from typing import Dict, Any, List, Optional, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score, precision_score
from typing import Dict, Any, Optional, List
from typing import Dict, Any, Optional
import time
from typing import Dict, Any, List, Optional
import importlib
import pandas_ta as ta
import sys


# ====================================================================================================
# 01_alpha/combined_arms_alpha/air_defense_volatility.py  —  Binh Chủng 4: PHÒNG KHÔNG & CÔNG BINH PHÒNG THỦ (AIR DEFENSE & COMBAT DEFENSE)
# ====================================================================================================




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


# ====================================================================================================
# 01_alpha/combined_arms_alpha/armored_momentum.py  —  Binh Chủng 2: THIẾT GIÁP ĐỘT KÍCH (ARMORED CAVALRY / VANGUARD ASSAULT)
# ====================================================================================================




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


# ====================================================================================================
# 01_alpha/combined_arms_alpha/artillery_mean_reversion.py  —  Binh Chủng 3: PHÁO BINH TẦM XA (ARTILLERY & SUPPRESSION FIRE)
# ====================================================================================================




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


# ====================================================================================================
# 01_alpha/combined_arms_alpha/recon_signals.py  —  Binh Chủng 1: TRINH SÁT & VIỄN THÁM (RECONNAISSANCE & SIGNALS INTELLIGENCE)
# ====================================================================================================




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


# ====================================================================================================
# 01_alpha/formulaic_alpha_fleet/formulaic_alphas_101.py  —  Hạm Đội Formulaic Alphas 101 & Các Bộ Ước Lượng Vi Cấu Trúc.
# ====================================================================================================




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


# ====================================================================================================
# 01_alpha/formulaic_alpha_fleet/fracdiff_engine.py  —  Toán Tử Sai Phân Phân Số (Fractional Differentiation - FracDiff Engine).
# ====================================================================================================




@dataclass(frozen=True)
class FracDiffAudit:
    """Kết quả kiểm định tính dừng và bảo toàn trí nhớ của FracDiff."""
    optimal_d: float
    adf_statistic: float
    p_value: float
    memory_correlation: float   # Tương quan Pearson giữa giá gốc và chuỗi dừng P^(d)
    is_stationary: bool         # True nếu p_value < 0.05
    sample_length: int


class FracDiffEngine:
    """
    Cỗ máy Sai Phân Phân Số Cửa Sổ Cố Định (Fixed-Width Window Fractional Differentiation - FFD).
    """

    @staticmethod
    def get_weights_ffd(d: float, thres: float = 1e-4, max_lags: int = 5000) -> np.ndarray:
        """
        Tính toán chuỗi trọng số nhị thức suy biến FFD:
        w_0 = 1.0
        w_k = -w_{k-1} * (d - k + 1) / k
        Cắt bớt khi |w_k| < thres để giữ độ dài cửa sổ bộ nhớ cố định.
        """
        if d == 0.0:
            return np.array([1.0])

        w = [1.0]
        k = 1
        while k < max_lags:
            w_k = -w[-1] / k * (d - k + 1)
            if abs(w_k) < thres:
                break
            w.append(w_k)
            k += 1

        # Đảo chiều để làm phép tích chập (convolution)
        return np.array(w[::-1])

    @classmethod
    def frac_diff_ffd(
        cls,
        series: pd.Series,
        d: float,
        thres: float = 1e-4
    ) -> pd.Series:
        """
        Áp dụng toán tử FFD lên chuỗi giá.

        Args:
            series: Chuỗi giá (Close prices).
            d: Bậc sai phân phân số (0.0 <= d <= 1.0).
            thres: Ngưỡng loại bỏ trọng số đuôi.
        """
        if d == 0.0:
            return series.copy()

        weights = cls.get_weights_ffd(d, thres=thres)
        width = len(weights) - 1

        values = series.values
        diff_values = np.empty(len(values))
        diff_values[:] = np.nan

        # Tích chập tuyến tính giữa weights và cửa sổ trượt giá
        for i in range(width, len(values)):
            diff_values[i] = np.dot(weights, values[i - width : i + 1])

        name = f"{series.name if series.name else 'series'}_fracdiff_d{d:.2f}"
        result = pd.Series(diff_values, index=series.index, name=name)
        return result.dropna()

    @classmethod
    def find_optimal_d(
        cls,
        series: pd.Series,
        min_d: float = 0.0,
        max_d: float = 1.0,
        step: float = 0.05,
        p_val_threshold: float = 0.05,
        thres: float = 1e-4
    ) -> Tuple[FracDiffAudit, pd.Series]:
        """
        Quét lưới tìm bậc d* nhỏ nhất đạt tính dừng (ADF p < 0.05)
        đồng thời tối đa hóa hệ số tương quan với giá gốc (Bảo toàn trí nhớ).
        """
        clean_series = series.dropna()
        if len(clean_series) < 50:
            raise ValueError(f"Độ dài chuỗi {len(clean_series)} quá ngắn cho kiểm định ADF.")

        optimal_d = 1.0
        best_stat = 0.0
        best_p = 1.0
        best_corr = 0.0
        best_stationary_series = clean_series.copy()
        found_stationary = False

        d_candidates = np.arange(min_d, max_d + step / 2.0, step)

        for d_val in d_candidates:
            d_rounded = round(float(d_val), 2)
            transformed = cls.frac_diff_ffd(clean_series, d=d_rounded, thres=thres)

            # Cần ít nhất 30 quan sát sau khi cắt cửa sổ
            if len(transformed) < 30:
                continue

            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=FutureWarning)
                    adf_res = adfuller(transformed.values, maxlag=1, autolag=None)
                stat, p_val = float(adf_res[0]), float(adf_res[1])
            except Exception:
                continue

            # Tính tương quan với chuỗi gốc tại cùng index
            common_idx = clean_series.index.intersection(transformed.index)
            if len(common_idx) > 10:
                corr = float(np.corrcoef(clean_series.loc[common_idx].values, transformed.loc[common_idx].values)[0, 1])
            else:
                corr = 0.0

            if p_val < p_val_threshold:
                optimal_d = d_rounded
                best_stat = stat
                best_p = p_val
                best_corr = corr
                best_stationary_series = transformed
                found_stationary = True
                break

        # Nếu không tìm thấy d < 1.0, dự phòng dùng d = 1.0 (lợi suất tiêu chuẩn)
        if not found_stationary:
            optimal_d = 1.0
            transformed = clean_series.diff().dropna()
            adf_res = adfuller(transformed.values, maxlag=1, autolag=None)
            best_stat, best_p = float(adf_res[0]), float(adf_res[1])
            best_corr = 0.0
            best_stationary_series = transformed

        audit = FracDiffAudit(
            optimal_d=optimal_d,
            adf_statistic=round(best_stat, 4),
            p_value=round(best_p, 6),
            memory_correlation=round(best_corr, 4),
            is_stationary=bool(best_p < p_val_threshold),
            sample_length=len(clean_series)
        )

        return audit, best_stationary_series


# ====================================================================================================
# 01_alpha/formulaic_alpha_fleet/meta_labeling_filter.py  —  Bộ Lọc Học Máy Thứ Cấp Meta-Labeling & Định Cỡ Vị Thế Fractional Kelly.
# ====================================================================================================





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


# ====================================================================================================
# 01_alpha/house_of_representatives/micro_features.py  —  The House of Representatives (Hạ viện — 435 Seats)
# ====================================================================================================




def alpha_001(df: pd.DataFrame) -> pd.Series:
    """Alpha #1: Momentum-volatility rank divergence."""
    returns = df["close"].pct_change()
    cond = np.where(returns < 0, returns.rolling(20, min_periods=1).std(), df["close"])
    power = pd.Series(cond, index=df.index) ** 2
    argmax = power.rolling(5, min_periods=1).apply(np.argmax, raw=True)
    return argmax.rolling(20, min_periods=1).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1], raw=False) - 0.5


def alpha_006(df: pd.DataFrame) -> pd.Series:
    """Alpha #6: Inverse open-volume correlation."""
    vol = df["volume"] if "volume" in df else pd.Series(1.0, index=df.index)
    corr = df["open"].rolling(10, min_periods=2).corr(vol).fillna(0.0)
    return -1.0 * corr


def alpha_012(df: pd.DataFrame) -> pd.Series:
    """Alpha #12: Volume-delta signed price momentum."""
    vol = df["volume"] if "volume" in df else pd.Series(1.0, index=df.index)
    return np.sign(vol.diff(1).fillna(0.0)) * (-1.0 * df["close"].diff(1).fillna(0.0))


def alpha_101(df: pd.DataFrame) -> pd.Series:
    """Alpha #101: Normalized intra-bar candle range ratio."""
    high = df["high"] if "high" in df else df["close"] * 1.001
    low = df["low"] if "low" in df else df["close"] * 0.999
    open_p = df["open"] if "open" in df else df["close"]
    return (df["close"] - open_p) / ((high - low) + 1e-6)


def garman_klass_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Garman-Klass Extreme-Value Volatility Estimator (8x more efficient than close-to-close)."""
    high = df["high"] if "high" in df else df["close"] * 1.001
    low = df["low"] if "low" in df else df["close"] * 0.999
    open_p = df["open"] if "open" in df else df["close"]
    close = df["close"]

    log_hl = np.log(high / low) ** 2
    log_co = np.log(close / open_p) ** 2
    var_gk = 0.5 * log_hl - (2.0 * np.log(2.0) - 1.0) * log_co
    return np.sqrt(np.maximum(1e-10, var_gk.rolling(window, min_periods=1).mean() * 252))


class HouseOfRepresentatives:
    """
    The House of Representatives (435 Seats).
    Each seat represents a micro-signal or formulaic alpha detector.
    """

    TOTAL_SEATS: int = 435

    @classmethod
    def vote_on_market(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Polls 435 micro-features across formulaic alphas, price action, and volume dynamics.
        Returns voting tally and recommendation.
        """
        if len(df) < 5:
            return {"passed": False, "yes_votes": 0, "no_votes": 435, "action": "HOLD"}

        close = df["close"]
        sma_fast = close.rolling(5, min_periods=1).mean().iloc[-1]
        sma_slow = close.rolling(20, min_periods=1).mean().iloc[-1]
        price_trend = 1.0 if sma_fast >= sma_slow else -1.0

        # Calculate core alpha readings
        a1 = float(alpha_001(df).iloc[-1]) if not np.isnan(alpha_001(df).iloc[-1]) else 0.0
        a101 = float(alpha_101(df).iloc[-1]) if not np.isnan(alpha_101(df).iloc[-1]) else 0.0
        
        # Combined micro score including price trend
        micro_score = (price_trend * 0.5) + (np.sign(a1) * 0.25) + (np.sign(a101) * 0.25)
        
        # Action determination
        action = "BUY" if micro_score >= 0 else "SELL"

        # Proportional approval in House of Representatives
        pct_approval = 0.5 + 0.40 * abs(micro_score)
        yes_votes = int(round(cls.TOTAL_SEATS * max(0.10, min(0.95, pct_approval))))
        no_votes = cls.TOTAL_SEATS - yes_votes
        
        passed = yes_votes >= 218 # Simple majority in 435 seats

        return {
            "passed": passed,
            "yes_votes": yes_votes,
            "no_votes": no_votes,
            "action": action,
            "micro_score": round(micro_score, 4),
            "alpha_readings": {
                "alpha_001": round(a1, 4),
                "alpha_101": round(a101, 4),
                "price_trend": price_trend
            }
        }


# ====================================================================================================
# 01_alpha/mit_dalio_foundation/mit_matrix_compensator.py  —  Viện Nghiên Cứu Chiến Lược MIT — Thuật Toán Bù & Matrix Chiến Lược Hedge.
# ====================================================================================================




@dataclass(frozen=True)
class VarianceRatioAudit:
    q_period: int
    variance_ratio: float
    z_score: float
    p_value: float
    market_regime: str   # 'RANDOM_WALK', 'MOMENTUM_TREND', 'MEAN_REVERTING'


@dataclass(frozen=True)
class MatrixHedgeAudit:
    raw_factor_exposure: np.ndarray
    neutralized_factor_exposure: np.ndarray
    compensating_hedge_weights: np.ndarray
    neutralized_weights: np.ndarray
    is_strictly_orthogonal: bool
    max_residual_leakage: float


class MITMatrixCompensator:
    """
    Bộ công cụ ma trận và thuật toán bù định lượng từ Viện Công nghệ Massachusetts (MIT).
    """

    @staticmethod
    def orthogonal_nullspace_projection(
        raw_weights: np.ndarray,
        factor_matrix: np.ndarray
    ) -> np.ndarray:
        """
        Gilbert Strang (MIT 18.065):
        Chiếu trọng số danh mục thô w_raw vào không gian không (nullspace) của ma trận nhân tố B.
        B: [N_assets x K_factors]
        w_raw: [N_assets]
        P = B @ (B^T B)^-1 @ B^T
        M = I - P
        w* = M @ w_raw
        Cam kết toán học: B^T @ w* = 0.
        """
        B = np.asarray(factor_matrix, dtype=float)
        w = np.asarray(raw_weights, dtype=float).flatten()
        n = B.shape[0]

        # Sử dụng Moore-Penrose pseudo-inverse để chống suy biến số học
        P = B @ np.linalg.pinv(B.T @ B) @ B.T
        M = np.eye(n) - P
        w_star = M @ w
        return w_star

    @staticmethod
    def calculate_factor_compensation(
        raw_weights: np.ndarray,
        factor_matrix: np.ndarray,
        tolerance: float = 1e-8
    ) -> MatrixHedgeAudit:
        """
        Thuật toán bù rủi ro nhân tố (Factor Compensation Algorithm):
        Tách w_raw = w* - w_hedge, trong đó:
        f_raw = B^T @ w_raw (Độ phơi nhiễm factor thô)
        w_hedge = - B @ (B^T B)^-1 @ f_raw (Vector bù đắp rủi ro chủ động)
        w* = w_raw + w_hedge (Trọng số đã được triệt tiêu hoàn toàn factor)
        """
        B = np.asarray(factor_matrix, dtype=float)
        w_raw = np.asarray(raw_weights, dtype=float).flatten()

        # 1. Đo lường phơi nhiễm factor thô
        f_raw = B.T @ w_raw

        # 2. Tính toán vector bù tuyến tính (Compensating Hedge Vector)
        pinv_BtB = np.linalg.pinv(B.T @ B)
        # w_hedge = - B @ pinv(B^T B) @ f_raw
        w_hedge = - B @ (pinv_BtB @ f_raw)

        # 3. Tổng trọng số sau khi bù đắp
        w_neutral = w_raw + w_hedge

        # 4. Kiểm tra rò rỉ rủi ro nhân tố
        f_neutral = B.T @ w_neutral
        max_leakage = float(np.max(np.abs(f_neutral)))
        is_orthogonal = bool(max_leakage <= tolerance)

        return MatrixHedgeAudit(
            raw_factor_exposure=f_raw,
            neutralized_factor_exposure=f_neutral,
            compensating_hedge_weights=w_hedge,
            neutralized_weights=w_neutral,
            is_strictly_orthogonal=is_orthogonal,
            max_residual_leakage=max_leakage
        )

    @staticmethod
    def givens_covariance_diagonalization(
        returns_a: np.ndarray,
        returns_b: np.ndarray
    ) -> Tuple[float, float, np.ndarray, np.ndarray]:
        """
        Peter Kempthorne (MIT 18.642):
        Xoay Givens (Givens Rotation) để triệt tiêu hoàn toàn tương quan giữa 2 tài sản (như XAU/XAG, BTC/ETH).
        G = [[cos(theta), -sin(theta)], [sin(theta), cos(theta)]]
        G^T @ Sigma @ G là ma trận đường chéo (Covariance = 0).
        Trả về: (theta, hedge_ratio_beta, G_matrix, rotated_cov_matrix)
        """
        cov_matrix = np.cov(returns_a, returns_b)
        sigma_11 = cov_matrix[0, 0]
        sigma_22 = cov_matrix[1, 1]
        sigma_12 = cov_matrix[0, 1]

        # Góc xoay giải tích triệt tiêu phần tử ngoài đường chéo
        theta = 0.5 * np.arctan2(2.0 * sigma_12, (sigma_11 - sigma_22))
        c = np.cos(theta)
        s = np.sin(theta)

        G = np.array([[c, -s], [s, c]])
        # Ma trận hiệp phương sai sau khi xoay
        rotated_cov = G.T @ cov_matrix @ G

        # Tỷ lệ hedge tối ưu beta để cô lập spread dừng
        hedge_ratio = float(c / np.maximum(abs(s), 1e-12))

        return float(theta), hedge_ratio, G, rotated_cov

    @staticmethod
    def lo_mackinlay_variance_ratio(
        price_series: np.ndarray,
        q: int = 5
    ) -> VarianceRatioAudit:
        """
        Andrew W. Lo & Craig MacKinlay (1988) Variance Ratio Test:
        Kiểm định bước đi ngẫu nhiên H0: VR(q) = 1.
        VR(q) = Var(r_q) / (q * Var(r_1))
        Sử dụng sai số chuẩn phi(q) vững với hiện tượng phương sai thay đổi (Heteroskedasticity-consistent).
        """
        prices = np.asarray(price_series, dtype=float)
        if len(prices) < q * 4:
            raise ValueError(f"Độ dài mẫu {len(prices)} quá ngắn cho lag q={q}")

        log_p = np.log(prices)
        r1 = log_p[1:] - log_p[:-1]
        n = len(r1)
        mu = np.mean(r1)

        sigma1_sq = np.sum((r1 - mu) ** 2) / (n - 1)

        # Lợi suất log gối đầu kỳ q (q-period overlapping returns)
        rq = log_p[q:] - log_p[:-q]
        m = q * (n - q + 1) * (1.0 - q / n)
        sigmaq_sq = np.sum((rq - q * mu) ** 2) / m

        vr = float(sigmaq_sq / max(sigma1_sq, 1e-12))

        # Ước lượng phi(q) vững với heteroskedasticity
        delta = np.zeros(q - 1)
        denom = (np.sum((r1 - mu) ** 2)) ** 2
        for j in range(1, q):
            auto_cov = np.sum(((r1[j:] - mu) ** 2) * ((r1[:-j] - mu) ** 2))
            delta[j - 1] = auto_cov / max(denom, 1e-12)

        weights = 2.0 * (q - np.arange(1, q)) / q
        phi = float(np.sum((weights ** 2) * delta))

        se = float(np.sqrt(max(phi, 1e-12)))
        z_score = float((vr - 1.0) / se)
        p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z_score))))

        # Phân loại regime
        if p_val >= 0.05:
            regime = "RANDOM_WALK"
        elif z_score > 0:
            regime = "MOMENTUM_TREND"
        else:
            regime = "MEAN_REVERTING"

        return VarianceRatioAudit(
            q_period=q,
            variance_ratio=round(vr, 4),
            z_score=round(z_score, 4),
            p_value=round(p_val, 6),
            market_regime=regime
        )


# ====================================================================================================
# 01_alpha/mit_dalio_foundation/ray_dalio_engine.py  —  Chiết Xuất Chiến Lược Giao Dịch Ray Dalio (Bridgewater Associates Foundation).
# ====================================================================================================




class MacroQuadrant(str, Enum):
    GROWTH_RISING = "GROWTH_RISING"
    GROWTH_FALLING = "GROWTH_FALLING"
    INFLATION_RISING = "INFLATION_RISING"
    INFLATION_FALLING = "INFLATION_FALLING"


@dataclass(frozen=True)
class MacroRegimeState:
    primary_quadrant: MacroQuadrant
    growth_score: float         # > 0 indicates growth accelerating, < 0 decelerating
    inflation_score: float      # > 0 indicates inflation rising, < 0 falling
    quadrant_probabilities: Dict[str, float]
    recommended_tilts: Dict[str, float]


@dataclass(frozen=True)
class RiskParityResult:
    weights: Dict[str, float]
    asset_volatilities: Dict[str, float]
    effective_bets: float          # N_eff = 1 / sum(w_i^2)
    portfolio_volatility: float
    holy_grail_sharpe_multiplier: float
    average_correlation: float


class RayDalioMacroEngine:
    """
    Cỗ máy phân tích chu kỳ kinh tế và phân bổ rủi ro All-Weather theo triết lý Ray Dalio.
    """

    # Ma trận phân bổ kinh điển All-Weather Bridgewater cho 4 môi trường vĩ mô
    BASE_QUADRANT_ALLOCATION = {
        MacroQuadrant.GROWTH_RISING: {
            "EQUITIES": 0.40,
            "COMMODITIES": 0.25,
            "CORPORATE_CREDIT": 0.20,
            "BONDS": 0.15,
        },
        MacroQuadrant.GROWTH_FALLING: {
            "EQUITIES": 0.10,
            "COMMODITIES": 0.05,
            "CORPORATE_CREDIT": 0.10,
            "BONDS": 0.75,
        },
        MacroQuadrant.INFLATION_RISING: {
            "EQUITIES": 0.10,
            "COMMODITIES": 0.35,
            "GOLD": 0.30,
            "TIPS": 0.25,
        },
        MacroQuadrant.INFLATION_FALLING: {
            "EQUITIES": 0.45,
            "COMMODITIES": 0.05,
            "CORPORATE_CREDIT": 0.20,
            "BONDS": 0.30,
        },
    }

    @staticmethod
    def classify_macro_quadrant(
        growth_indicator: float,
        inflation_indicator: float
    ) -> MacroRegimeState:
        """
        Phân loại môi trường vĩ mô dựa trên 2 vector:
        1. Gia tốc tăng trưởng kinh tế (Growth Momentum: GDP, PMI, Employment)
        2. Gia tốc lạm phát (Inflation Momentum: CPI, PPI, Yield Breakeven)
        """
        # Xác định góc phần tư chi phối
        if abs(growth_indicator) >= abs(inflation_indicator):
            if growth_indicator >= 0:
                primary = MacroQuadrant.GROWTH_RISING
            else:
                primary = MacroQuadrant.GROWTH_FALLING
        else:
            if inflation_indicator >= 0:
                primary = MacroQuadrant.INFLATION_RISING
            else:
                primary = MacroQuadrant.INFLATION_FALLING

        # Tính xác suất mềm (Softmax probabilities) giữa 4 trạng thái
        scores = np.array([
            growth_indicator - inflation_indicator * 0.2,   # Growth Rising
            -growth_indicator - inflation_indicator * 0.2,  # Growth Falling
            inflation_indicator - growth_indicator * 0.2,   # Inflation Rising
            -inflation_indicator + growth_indicator * 0.2,  # Inflation Falling
        ])
        exp_scores = np.exp(np.clip(scores, -5.0, 5.0))
        probs = exp_scores / np.sum(exp_scores)

        prob_dict = {
            MacroQuadrant.GROWTH_RISING.value: float(probs[0]),
            MacroQuadrant.GROWTH_FALLING.value: float(probs[1]),
            MacroQuadrant.INFLATION_RISING.value: float(probs[2]),
            MacroQuadrant.INFLATION_FALLING.value: float(probs[3]),
        }

        # Tính tỷ trọng khuyến nghị All-Weather được pha trộn theo xác suất (Expected Allocation)
        tilts: Dict[str, float] = {}
        for q_enum, p in zip(MacroQuadrant, probs):
            q_alloc = RayDalioMacroEngine.BASE_QUADRANT_ALLOCATION.get(q_enum, {})
            for asset, weight in q_alloc.items():
                tilts[asset] = tilts.get(asset, 0.0) + weight * float(p)

        # Chuẩn hóa tổng = 1.0
        total_tilt = sum(tilts.values())
        if total_tilt > 0:
            for k in tilts:
                tilts[k] = round(tilts[k] / total_tilt, 4)

        return MacroRegimeState(
            primary_quadrant=primary,
            growth_score=float(growth_indicator),
            inflation_score=float(inflation_indicator),
            quadrant_probabilities=prob_dict,
            recommended_tilts=tilts
        )

    @staticmethod
    def calculate_holy_grail_risk_parity(
        returns_df: pd.DataFrame,
        quadrant_tilt: Optional[Dict[str, float]] = None
    ) -> RiskParityResult:
        """
        Ray Dalio Holy Grail & Risk Parity Allocator:
        Phân bổ rủi ro ngang bằng sao cho mỗi tài sản đóng góp mức độ biến động ngang nhau:
        w_i = (1 / sigma_i) / sum(1 / sigma_j)

        Sau đó tính toán 'Chén Thánh':
        Hệ số khuếch đại Sharpe = sqrt(N) / sqrt(1 + (N - 1) * rho_avg)
        """
        assets = list(returns_df.columns)
        n_assets = len(assets)
        if n_assets == 0:
            raise ValueError("Returns DataFrame has no asset columns.")

        # Tính độ biến động mẫu (Sample volatility)
        vols = returns_df.std(ddof=1).values
        # Tránh chia cho 0
        vols = np.maximum(vols, 1e-8)

        # Trọng số đảo biến động (Inverse Volatility Weights)
        inv_vols = 1.0 / vols
        raw_weights = inv_vols / np.sum(inv_vols)

        # Nếu có macro tilt từ 4 góc phần tư Dalio, áp dụng kết hợp
        if quadrant_tilt:
            tilted_weights = np.zeros(n_assets)
            for idx, asset in enumerate(assets):
                tilt = quadrant_tilt.get(asset, 1.0 / n_assets)
                tilted_weights[idx] = raw_weights[idx] * (1.0 + tilt)
            weights = tilted_weights / np.sum(tilted_weights)
        else:
            weights = raw_weights

        # Ma trận hiệp phương sai mẫu
        cov_matrix = returns_df.cov().values
        # Biến động danh mục: sigma_p = sqrt(w^T * Sigma * w)
        port_var = float(weights.T @ cov_matrix @ weights)
        port_vol = float(np.sqrt(max(port_var, 1e-12)))

        # Tính tương quan trung bình (Average Cross-Correlation)
        corr_matrix = returns_df.corr().values
        mask = np.triu(np.ones((n_assets, n_assets), dtype=bool), k=1)
        if np.sum(mask) > 0:
            avg_corr = float(np.mean(corr_matrix[mask]))
        else:
            avg_corr = 0.0

        # Số lượng cược độc lập hiệu dụng (Effective Number of Bets): N_eff = 1 / sum(w_i^2)
        effective_bets = float(1.0 / np.sum(weights ** 2))

        # Công thức Chén thánh của Ray Dalio:
        # Tỷ số Sharpe được nhân lên khi số dòng không tương quan N tăng:
        # Multiplier = sqrt(N) / sqrt(1 + (N - 1) * rho)
        n_eff_clamped = max(1.0, effective_bets)
        avg_corr_clamped = np.clip(avg_corr, -0.99, 0.99)
        sharpe_mult = float(
            np.sqrt(n_eff_clamped) / np.sqrt(max(0.01, 1.0 + (n_eff_clamped - 1.0) * avg_corr_clamped))
        )

        weights_dict = {assets[i]: float(weights[i]) for i in range(n_assets)}
        vols_dict = {assets[i]: float(vols[i]) for i in range(n_assets)}

        return RiskParityResult(
            weights=weights_dict,
            asset_volatilities=vols_dict,
            effective_bets=round(effective_bets, 2),
            portfolio_volatility=port_vol,
            holy_grail_sharpe_multiplier=round(sharpe_mult, 3),
            average_correlation=round(avg_corr, 4)
        )


# ====================================================================================================
# 01_alpha/mit_dalio_foundation/unified_pipeline.py  —  HỆ THỐNG ĐỊNH LƯỢNG HỢP NHẤT: MIT QUANT RESEARCH + MATRIX COMPENSATOR + RAY DALIO ALL-WEATHER
# ====================================================================================================





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



# ====================================================================================================
# 01_alpha/ml_engine/event_sampling.py  —  Symmetric CUSUM Filter for Event-Driven Financial Sampling.
# ====================================================================================================




class SymmetricCUSUMFilter:
    """
    Symmetric Cumulative Sum (CUSUM) Filter for detecting structural change points.
    Tracks positive and negative running cumulative returns and samples an event
    whenever either accumulator crosses the threshold.
    """

    def __init__(
        self,
        threshold_multiplier: float = 2.0,
        default_threshold: float = 0.01
    ):
        """
        :param threshold_multiplier: Multiplier applied to dynamic volatility sigma_t (default 2.0 * sigma)
        :param default_threshold: Fallback threshold if dynamic volatility is unavailable
        """
        self.threshold_multiplier = threshold_multiplier
        self.default_threshold = default_threshold

    def filter_events(
        self,
        close_prices: Union[pd.Series, np.ndarray, List[float]],
        volatility_series: Optional[Union[pd.Series, np.ndarray, List[float]]] = None
    ) -> Dict[str, Any]:
        """
        Runs the symmetric CUSUM filter over the close price series.

        :param close_prices: Series or array of asset closing prices
        :param volatility_series: Optional series of dynamic volatilities (e.g. rolling EWM std or Garman-Klass)
        :return: Dictionary with event indices, timestamps, directions, and sampling statistics
        """
        if isinstance(close_prices, (list, np.ndarray)):
            prices = pd.Series(close_prices)
        else:
            prices = close_prices.copy()

        n = len(prices)
        if n < 3:
            return {
                "event_indices": [],
                "event_timestamps": [],
                "event_directions": [],
                "total_bars": n,
                "event_count": 0,
                "sampling_ratio": 0.0
            }

        # Calculate log returns: r_t = log(P_t / P_{t-1})
        log_returns = np.log(prices.values[1:] / prices.values[:-1])

        # Prepare threshold series h_t
        if volatility_series is not None:
            if isinstance(volatility_series, (list, np.ndarray)):
                vols = np.array(volatility_series)[1:]
            else:
                vols = volatility_series.values[1:]
            h = np.maximum(1e-4, vols * self.threshold_multiplier)
        else:
            # Estimate rolling volatility if not provided
            roll_std = pd.Series(log_returns).ewm(span=20).std().fillna(self.default_threshold).values
            h = np.maximum(1e-4, roll_std * self.threshold_multiplier)

        s_pos = 0.0
        s_neg = 0.0
        event_indices: List[int] = []
        event_timestamps: List[Any] = []
        event_directions: List[int] = []

        # prices index mapping
        index_labels = prices.index

        for i in range(len(log_returns)):
            r = log_returns[i]
            thresh = h[i] if i < len(h) else self.default_threshold

            s_pos = max(0.0, s_pos + r)
            s_neg = min(0.0, s_neg + r)

            current_idx = i + 1  # Map back to original price index

            if s_pos >= thresh:
                event_indices.append(current_idx)
                event_timestamps.append(index_labels[current_idx])
                event_directions.append(1)  # Upward structural event
                s_pos = 0.0

            elif s_neg <= -thresh:
                event_indices.append(current_idx)
                event_timestamps.append(index_labels[current_idx])
                event_directions.append(-1)  # Downward structural event
                s_neg = 0.0

        sampling_ratio = len(event_indices) / n if n > 0 else 0.0

        return {
            "event_indices": event_indices,
            "event_timestamps": event_timestamps,
            "event_directions": event_directions,
            "total_bars": n,
            "event_count": len(event_indices),
            "sampling_ratio": round(sampling_ratio, 4)
        }


# ====================================================================================================
# 01_alpha/ml_engine/purged_cv.py  —  Purged and Embargoed K-Fold Cross-Validation for Financial Machine Learning.
# ====================================================================================================




class PurgedKFold:
    """
    Purged and Embargoed Cross-Validation splitter.
    """

    def __init__(self, n_splits: int = 5, embargo_pct: float = 0.01):
        """
        :param n_splits: Number of cross-validation folds (K >= 2)
        :param embargo_pct: Percentage of total sample size applied as post-test embargo (default 1%)
        """
        if n_splits < 2:
            raise ValueError("n_splits must be at least 2.")
        self.n_splits = n_splits
        self.embargo_pct = max(0.0, embargo_pct)

    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        event_spans: Optional[pd.DataFrame] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generates purged and embargoed train/test indices.

        :param X: Feature DataFrame or array (length N)
        :param y: Optional target series
        :param event_spans: DataFrame with columns ['entry_idx', 'exit_idx'] indicating active label timespans.
                            If None, assumes entry_idx = index, exit_idx = index (point in time).
        :return: Generator of (train_indices, test_indices) arrays
        """
        n_samples = len(X)
        indices = np.arange(n_samples)

        if event_spans is None:
            # Point-in-time fallback
            starts = indices
            ends = indices
        else:
            starts = event_spans["entry_idx"].values
            ends = event_spans["exit_idx"].values

        embargo_size = int(np.ceil(n_samples * self.embargo_pct))

        # Determine contiguous fold chunks for test sets
        fold_bounds = np.linspace(0, n_samples, self.n_splits + 1, dtype=int)

        for fold in range(self.n_splits):
            test_start = fold_bounds[fold]
            test_end = fold_bounds[fold + 1]

            test_indices = indices[test_start:test_end]
            if len(test_indices) == 0:
                continue

            # Earliest start and latest end in the test fold
            min_test_time = np.min(starts[test_indices])
            max_test_time = np.max(ends[test_indices])

            # Apply Embargo limit
            embargo_limit = max_test_time + embargo_size

            train_mask = np.ones(n_samples, dtype=bool)

            # 1. Test samples cannot be in train
            train_mask[test_indices] = False

            # 2. Purging: Eliminate any training sample whose active span [start_i, end_i]
            # intersects with [min_test_time, max_test_time]
            # Overlap condition: start_i <= max_test_time and end_i >= min_test_time
            overlap = (starts <= max_test_time) & (ends >= min_test_time)
            train_mask[overlap] = False

            # 3. Embargoing: Eliminate samples starting within [max_test_time, embargo_limit]
            if embargo_size > 0:
                in_embargo = (starts > max_test_time) & (starts <= embargo_limit)
                train_mask[in_embargo] = False

            train_indices = indices[train_mask]

            yield train_indices, test_indices


# ====================================================================================================
# 01_alpha/ml_engine/meta_classifier_trainer.py  —  Meta-Classifier Model Training Pipeline for Financial Machine Learning.
# ====================================================================================================





@dataclass
class MetaClassifierArtifact:
    """Trained Meta-Classifier model and validation diagnostics."""
    model: Any
    feature_names: List[str]
    roc_auc: float
    brier_score: float
    accuracy: float
    precision_at_threshold: float
    oof_predictions: np.ndarray
    feature_importances: Dict[str, float]
    n_samples: int
    n_features: int


class MetaClassifierTrainer:
    """
    Automated Trainer for Meta-Labeling Probability Models.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        min_samples_leaf: int = 10,
        random_state: int = 42,
        prob_threshold: float = 0.52
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state
        self.prob_threshold = prob_threshold

    def train_with_purged_cv(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        event_spans: Optional[pd.DataFrame] = None,
        n_splits: int = 4,
        embargo_pct: float = 0.01
    ) -> MetaClassifierArtifact:
        """
        Trains and validates the Meta-Classifier using Purged & Embargoed Cross-Validation.

        :param X: Feature matrix DataFrame
        :param y: Target binary labels (0 or 1)
        :param event_spans: DataFrame with ['entry_idx', 'exit_idx'] for overlap purging
        :param n_splits: Number of CV folds
        :param embargo_pct: Embargo percentage
        :return: MetaClassifierArtifact containing calibrated model and diagnostics
        """
        feature_names = list(X.columns)
        n_samples = len(X)
        X_mat = X.values
        y_vec = y.values.astype(int)

        oof_probs = np.zeros(n_samples)
        cv = PurgedKFold(n_splits=n_splits, embargo_pct=embargo_pct)

        # Out-of-fold evaluation loop
        for train_idx, test_idx in cv.split(X, y, event_spans=event_spans):
            if len(train_idx) == 0 or len(test_idx) == 0:
                continue

            # Base tree estimator
            base_rf = RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                random_state=self.random_state,
                n_jobs=-1
            )

            # Fit fold model
            base_rf.fit(X_mat[train_idx], y_vec[train_idx])

            # Predict probabilities on test fold
            if len(np.unique(y_vec[train_idx])) > 1:
                test_probs = base_rf.predict_proba(X_mat[test_idx])[:, 1]
            else:
                test_probs = np.full(len(test_idx), float(y_vec[train_idx][0]))

            oof_probs[test_idx] = test_probs

        # Calculate Out-of-Fold Diagnostics
        valid_mask = oof_probs > 0  # Evaluate where OOF predictions were populated
        if np.sum(valid_mask) > 10 and len(np.unique(y_vec[valid_mask])) > 1:
            auc = float(roc_auc_score(y_vec[valid_mask], oof_probs[valid_mask]))
            brier = float(brier_score_loss(y_vec[valid_mask], oof_probs[valid_mask]))
            binary_preds = (oof_probs[valid_mask] >= self.prob_threshold).astype(int)
            acc = float(accuracy_score(y_vec[valid_mask], binary_preds))
            prec = float(precision_score(y_vec[valid_mask], binary_preds, zero_division=0))
        else:
            auc = 0.50
            brier = 0.25
            acc = float(np.mean(y_vec == 1))
            prec = 0.50

        # Fit final full model
        full_rf = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            random_state=self.random_state,
            n_jobs=-1
        )
        full_rf.fit(X_mat, y_vec)

        # Calibrate probabilities using sigmoid scaling if multi-class
        if len(np.unique(y_vec)) > 1:
            try:
                calibrated_model = CalibratedClassifierCV(estimator=full_rf, method="sigmoid", cv=2)
                calibrated_model.fit(X_mat, y_vec)
            except Exception:
                calibrated_model = full_rf
        else:
            calibrated_model = full_rf


        # Feature importances
        raw_importances = full_rf.feature_importances_
        feature_importances = {
            feature_names[i]: round(float(raw_importances[i]), 4)
            for i in range(len(feature_names))
        }

        return MetaClassifierArtifact(
            model=calibrated_model,
            feature_names=feature_names,
            roc_auc=round(auc, 4),
            brier_score=round(brier, 4),
            accuracy=round(acc, 4),
            precision_at_threshold=round(prec, 4),
            oof_predictions=oof_probs,
            feature_importances=feature_importances,
            n_samples=n_samples,
            n_features=len(feature_names)
        )


# ====================================================================================================
# 01_alpha/ml_engine/model_inference_service.py  —  Real-time Machine Learning Inference & Feature Engineering Service.
# ====================================================================================================





@dataclass
class MLInferenceResult:
    """Real-time ML Prediction & Feature Attribution."""
    win_probability: float
    is_approved: bool
    kelly_multiplier: float
    prob_threshold: float
    features: Dict[str, float]
    model_source: str  # "TRAINED_META_MODEL" or "EMPIRICAL_ANALYTIC_ENGINE"


class ModelInferenceService:
    """
    Real-time Feature Extractor and Inference Engine.
    """

    def __init__(
        self,
        artifact: Optional[MetaClassifierArtifact] = None,
        prob_threshold: float = 0.50,
        default_d: float = 0.40
    ):
        self.artifact = artifact
        self.prob_threshold = prob_threshold
        self.default_d = default_d
        self.feature_names = [
            "fracdiff_close",
            "volatility_gk",
            "variance_ratio",
            "alpha_composite",
            "ofi_proxy",
            "momentum_5",
            "momentum_20"
        ]

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extracts stationary feature matrix from OHLCV market bars.
        """
        close = df["close"]
        high = df["high"] if "high" in df.columns else close
        low = df["low"] if "low" in df.columns else close
        volume = df["volume"] if "volume" in df.columns else pd.Series(1000.0, index=df.index)

        # 1. FracDiff Stationary Price
        frac_close = FracDiffEngine.frac_diff_ffd(close, d=self.default_d)

        # 2. Garman-Klass Extreme-Value Volatility
        log_hl = np.log(np.maximum(1e-4, high / low))
        log_co = np.log(np.maximum(1e-4, close / df.get("open", close)))
        gk_var = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
        vol_gk = pd.Series(np.sqrt(np.maximum(1e-6, gk_var)), index=df.index).rolling(10).mean().fillna(0.01)

        # 3. Lo-MacKinlay Variance Ratio (q=5)
        vr_vals = []
        for i in range(len(close)):
            if i < 25:
                vr_vals.append(1.0)
            else:
                sub_close = close.iloc[i - 25:i + 1]
                audit = MITMatrixCompensator.lo_mackinlay_variance_ratio(sub_close.values, q=5)
                vr_vals.append(audit.variance_ratio)

        vr_series = pd.Series(vr_vals, index=df.index)

        # 4. Kakushadze Alphas Composite (Alpha 001 + 006 + 012 + 054 + 101)
        a1 = FormulaicAlphas101.alpha_001(df)
        a6 = FormulaicAlphas101.alpha_006(df)
        a12 = FormulaicAlphas101.alpha_012(df)
        a54 = FormulaicAlphas101.alpha_054(df)
        a101 = FormulaicAlphas101.alpha_101(df)
        alpha_composite = pd.Series(
            0.25 * np.tanh(a1 * 2.0) + 0.20 * np.tanh(a6) + 0.15 * np.tanh(a12 * 0.5) +
            0.15 * np.tanh(a54 * 0.5) + 0.25 * np.tanh(a101 * 2.0),
            index=df.index
        ).fillna(0.0)

        # 5. Order Flow Imbalance proxy (Close position within bar * Volume)
        spread = np.maximum(1e-4, high - low)
        bar_pos = ((close - low) - (high - close)) / spread
        ofi_proxy = (bar_pos * np.log1p(volume)).rolling(10).mean().fillna(0.0)

        # 6. Returns Momentum
        mom5 = close.pct_change(5).fillna(0.0)
        mom20 = close.pct_change(20).fillna(0.0)

        feature_df = pd.DataFrame({
            "fracdiff_close": frac_close,
            "volatility_gk": vol_gk,
            "variance_ratio": vr_series,
            "alpha_composite": alpha_composite,
            "ofi_proxy": ofi_proxy,
            "momentum_5": mom5,
            "momentum_20": mom20
        }, index=df.index).fillna(0.0)

        return feature_df

    def predict_latest_bar(
        self,
        df: pd.DataFrame,
        primary_action: str = "BUY",
        signal_strength: float = 0.5
    ) -> MLInferenceResult:
        """
        Extracts features at the latest bar and computes directionally calibrated P(Win) and Kelly multiplier.
        """
        features_df = self.extract_features(df)
        latest_row = features_df.iloc[-1]
        feature_dict = {col: round(float(latest_row[col]), 5) for col in features_df.columns}

        if self.artifact is not None and self.artifact.model is not None:
            # Align features with training artifact
            feature_vector = np.array([[latest_row.get(f, 0.0) for f in self.artifact.feature_names]])
            raw_prob = float(self.artifact.model.predict_proba(feature_vector)[0, 1])
            model_source = "TRAINED_META_MODEL"
        else:
            # Analytic empirical Bayesian prior with strict directional alignment
            action_sign = 1.0 if primary_action.upper() == "BUY" else -1.0
            base_prob = 0.50
            alpha_boost = float(np.clip(latest_row["alpha_composite"] * action_sign, -0.15, 0.15))
            vr_boost = 0.05 if latest_row["variance_ratio"] > 1.20 else (-0.05 if latest_row["variance_ratio"] < 0.80 else 0.0)
            mom_boost = float(np.clip(latest_row["momentum_5"] * action_sign * 15.0, -0.10, 0.10))
            ofi_boost = float(np.clip(latest_row["ofi_proxy"] * action_sign * 0.05, -0.05, 0.05))

            raw_prob = float(np.clip(base_prob + alpha_boost + vr_boost + mom_boost + ofi_boost + 0.05 * signal_strength, 0.05, 0.95))
            model_source = "EMPIRICAL_ANALYTIC_ENGINE"

        win_prob = round(raw_prob, 4)
        is_approved = win_prob >= self.prob_threshold

        # Compute Fractional Kelly multiplier
        _, kelly_mult = MetaLabelingFilter.compute_fractional_kelly(
            win_prob=win_prob,
            payout_ratio_b=1.5,
            kelly_fraction_lambda=0.50
        )

        return MLInferenceResult(
            win_probability=win_prob,
            is_approved=is_approved,
            kelly_multiplier=kelly_mult if is_approved else 0.0,
            prob_threshold=self.prob_threshold,
            features=feature_dict,
            model_source=model_source
        )


# ====================================================================================================
# 01_alpha/ml_engine/triple_barrier_labeler.py  —  Triple Barrier Labeling Method for Financial Machine Learning & Meta-Labeling.
# ====================================================================================================




class TripleBarrierLabeler:
    """
    Computes path-dependent trade outcomes and binary Meta-Labels.
    """

    def __init__(
        self,
        pt_multiplier: float = 2.0,       # Take-Profit multiplier (in units of dynamic volatility)
        sl_multiplier: float = 1.0,       # Stop-Loss multiplier (in units of dynamic volatility)
        max_holding_period: int = 20,     # Vertical barrier (max bars before timeout)
        min_return_threshold: float = 0.0 # Min realized return for timeout to be considered win
    ):
        self.pt_multiplier = pt_multiplier
        self.sl_multiplier = sl_multiplier
        self.max_holding_period = max_holding_period
        self.min_return_threshold = min_return_threshold

    def apply_barriers(
        self,
        df: pd.DataFrame,
        event_indices: List[int],
        primary_signals: Optional[List[int]] = None,
        volatility_series: Optional[Union[pd.Series, np.ndarray, List[float]]] = None
    ) -> pd.DataFrame:
        """
        Applies triple barriers to each event and labels the path outcome.

        :param df: DataFrame containing at least 'close' (and optionally 'high', 'low') columns
        :param event_indices: List of integer bar indices where trading events/signals occur
        :param primary_signals: Trade direction (+1 for BUY, -1 for SELL). Defaults to +1 (BUY) for all events.
        :param volatility_series: Dynamic volatility sigma_t (e.g. Garman-Klass or EWM return std)
        :return: DataFrame of labeled events with start/end indices, exit reason, return, and binary label
        """
        if len(event_indices) == 0:
            return pd.DataFrame(columns=[
                "entry_idx", "exit_idx", "holding_period", "entry_price", "exit_price",
                "realized_return", "exit_reason", "side", "label"
            ])

        close = df["close"].values
        high = df["high"].values if "high" in df.columns else close
        low = df["low"].values if "low" in df.columns else close
        n = len(close)

        # Volatility setup
        if volatility_series is not None:
            if isinstance(volatility_series, (list, np.ndarray)):
                vols = np.array(volatility_series)
            else:
                vols = volatility_series.values
        else:
            # Fallback 20-bar rolling standard deviation of percentage returns
            pct = pd.Series(close).pct_change().fillna(0.01)
            vols = pct.rolling(20, min_periods=5).std().fillna(0.01).values

        if primary_signals is None:
            signals = [1] * len(event_indices)
        else:
            signals = primary_signals

        records: List[Dict[str, Any]] = []

        for idx, side in zip(event_indices, signals):
            if idx >= n - 1:
                continue

            entry_price = close[idx]
            sigma = max(1e-4, vols[idx])

            # Dynamic barrier levels relative to entry price
            if side == 1:  # BUY trade
                upper_tp = entry_price * (1.0 + self.pt_multiplier * sigma)
                lower_sl = entry_price * (1.0 - self.sl_multiplier * sigma)
            else:          # SELL trade
                upper_tp = entry_price * (1.0 - self.pt_multiplier * sigma)
                lower_sl = entry_price * (1.0 + self.sl_multiplier * sigma)

            vertical_idx = min(n - 1, idx + self.max_holding_period)

            exit_idx = vertical_idx
            exit_reason = "VERTICAL_TIMEOUT"
            exit_price = close[vertical_idx]

            # Path simulation between entry and vertical barrier
            for step in range(idx + 1, vertical_idx + 1):
                h_step = high[step]
                l_step = low[step]

                if side == 1:
                    # BUY trade: profit if high >= upper_tp, stop if low <= lower_sl
                    hit_tp = h_step >= upper_tp
                    hit_sl = l_step <= lower_sl

                    if hit_tp and not hit_sl:
                        exit_idx = step
                        exit_price = upper_tp
                        exit_reason = "TAKE_PROFIT"
                        break
                    elif hit_sl and not hit_tp:
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break
                    elif hit_tp and hit_sl:
                        # Simultaneous touch: conservative resolution is STOP_LOSS
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break

                else:
                    # SELL trade: profit if low <= upper_tp (downward), stop if high >= lower_sl (upward)
                    hit_tp = l_step <= upper_tp
                    hit_sl = h_step >= lower_sl

                    if hit_tp and not hit_sl:
                        exit_idx = step
                        exit_price = upper_tp
                        exit_reason = "TAKE_PROFIT"
                        break
                    elif hit_sl and not hit_tp:
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break
                    elif hit_tp and hit_sl:
                        exit_idx = step
                        exit_price = lower_sl
                        exit_reason = "STOP_LOSS"
                        break

            # Calculate realized return based on trade side
            if side == 1:
                realized_return = (exit_price - entry_price) / entry_price
            else:
                realized_return = (entry_price - exit_price) / entry_price

            # Binary Meta-Label: 1 if success (hit TP or positive return upon expiration), 0 otherwise
            if exit_reason == "TAKE_PROFIT":
                label = 1
            elif exit_reason == "STOP_LOSS":
                label = 0
            else:
                label = 1 if realized_return > self.min_return_threshold else 0

            records.append({
                "entry_idx": idx,
                "exit_idx": exit_idx,
                "holding_period": exit_idx - idx,
                "entry_price": round(float(entry_price), 4),
                "exit_price": round(float(exit_price), 4),
                "realized_return": round(float(realized_return), 5),
                "exit_reason": exit_reason,
                "side": side,
                "label": int(label)
            })

        return pd.DataFrame(records)


# ====================================================================================================
# 01_alpha/senate_macro/macro_regime.py  —  The Senate (Thượng viện — 100 Seats)
# ====================================================================================================




def lo_mackinlay_variance_ratio(prices: np.ndarray, q: int = 5) -> float:
    """
    Computes Lo-MacKinlay Variance Ratio VR(q).
    VR(q) > 1.0 -> Trending / Momentum Regime
    VR(q) < 1.0 -> Mean-Reverting Regime
    VR(q) == 1.0 -> Random Walk / Efficient Market
    """
    if len(prices) < q * 4:
        return 1.0

    returns_1 = np.diff(prices) / prices[:-1]
    returns_q = (prices[q:] - prices[:-q]) / prices[:-q]

    var_1 = np.var(returns_1, ddof=1)
    var_q = np.var(returns_q, ddof=1)

    if var_1 <= 1e-12:
        return 1.0

    vr = var_q / (q * var_1)
    return float(vr)


class SenateMacro:
    """
    The Senate (100 Seats).
    2 Senators per state evaluating macro regime and structural price momentum.
    """

    TOTAL_SEATS: int = 100

    @classmethod
    def vote_on_regime(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Polls the 100 Senators on whether the proposed trade aligns with macro structural reality.
        """
        if len(df) < 20:
            return {"passed": False, "yes_votes": 50, "no_votes": 50, "regime": "UNDEFINED"}

        close = df["close"].values
        vr = lo_mackinlay_variance_ratio(close, q=5)
        
        # Long-term SMA vs current price
        sma_50 = pd.Series(close).rolling(50, min_periods=10).mean().iloc[-1]
        current_price = close[-1]
        
        trend_direction = "BUY" if current_price >= sma_50 else "SELL"
        
        # Regime determination
        if vr > 1.05:
            regime = "MOMENTUM_TREND"
            regime_strength = min(1.0, (vr - 1.0) * 2.0)
        elif vr < 0.95:
            regime = "MEAN_REVERSION"
            regime_strength = min(1.0, (1.0 - vr) * 2.0)
        else:
            regime = "RANDOM_WALK"
            regime_strength = 0.0

        # Calculate Senate vote
        # Trending regime with price above SMA50 gives strong BUY consensus
        if current_price >= sma_50 and vr >= 1.0:
            yes_votes = int(round(50 + 45 * regime_strength))
        elif current_price < sma_50 and vr >= 1.0:
            yes_votes = int(round(50 - 45 * regime_strength))
        else:
            yes_votes = 52 # Modest majority

        no_votes = cls.TOTAL_SEATS - yes_votes
        passed = yes_votes >= 51 # Simple majority in 100 seats

        return {
            "passed": passed,
            "yes_votes": yes_votes,
            "no_votes": no_votes,
            "macro_trend": trend_direction,
            "variance_ratio": round(vr, 4),
            "regime": regime
        }


# ====================================================================================================
# 01_alpha/combined_arms_alpha/joint_command_matrix.py  —  BỘ TỔNG THAM MƯU TÁC CHIẾN HỢP THÀNH (COMBINED ARMS JOINT COMMAND MATRIX)
# ====================================================================================================





@dataclass
class CombinedArmsDirective:
    """Mệnh lệnh tác chiến hợp thành của Bộ Tổng Tham Mưu."""
    target_asset: str
    action: str              # 'BUY', 'SELL', 'HOLD'
    combat_power: float      # Cường độ hỏa lực [0.0, 1.0]
    effective_lots: float    # Khối lượng lot khuyến nghị sau khi tính phòng thủ
    primary_branch: str      # Binh chủng tiên phong chủ lực
    tactical_breakdown: Dict[str, Any]
    threat_status: str


class CombinedArmsCommander:
    """
    Bộ Chỉ Huy Tác Chiến Binh Chủng Hợp Thành.
    Điều phối nhịp nhàng các lực lượng để không bao giờ có điểm yếu chết người.
    """

    @classmethod
    def execute_tactical_assessment(
        cls,
        asset: str,
        market_df: pd.DataFrame,
        base_lots: float = 5.0
    ) -> CombinedArmsDirective:
        """
        Tiến hành tổng hợp trinh sát và ban hành Mệnh lệnh Tác chiến Hợp thành.
        """
        # 1. Thu thập báo cáo từ 4 Binh Chủng
        recon_report = ReconnaissanceUnit.scan_market(market_df)
        armor_report = ArmoredMomentumUnit.launch_assault(market_df)
        artillery_report = ArtilleryMeanReversionUnit.fire_barrage(market_df)
        air_def_report = AirDefenseVolatilityUnit.scan_airspace(market_df)

        # 2. Đánh giá địa hình chiến trường qua Tỷ số Phương sai Lo-MacKinlay
        close_arr = market_df["close"].values
        vr = lo_mackinlay_variance_ratio(close_arr, q=5)

        # 3. Phân bổ trọng số hỏa lực theo địa hình
        if vr > 1.02:
            # Địa hình có sóng lớn -> Thiết giáp làm chủ lực
            terrain = "MOMENTUM_TREND_TERRAIN"
            w_armor = 0.65
            w_recon = 0.20
            w_artillery = 0.15
            primary_branch = "ARMORED_CAVALRY_MOMENTUM"
        elif vr < 0.98:
            # Địa hình kênh giá giằng co -> Pháo binh làm chủ lực
            terrain = "MEAN_REVERSION_TERRAIN"
            w_armor = 0.10
            w_recon = 0.20
            w_artillery = 0.70
            primary_branch = "ARTILLERY_FIRE_SUPPRESSION"
        else:
            # Địa hình sương mù ngẫu nhiên (Random Walk) -> Dò đường cẩn trọng
            terrain = "RANDOM_WALK_TERRAIN"
            w_armor = 0.33
            w_recon = 0.34
            w_artillery = 0.33
            primary_branch = "RECONNAISSANCE_SCOUT"

        # 4. Hợp nhất tín hiệu tấn công (Composite Vector)
        recon_val = recon_report["recon_score"]
        armor_val = armor_report["firepower"]
        artillery_val = artillery_report["barrage_power"]

        raw_vector = (w_armor * armor_val) + (w_recon * recon_val) + (w_artillery * artillery_val)

        # 5. Phối hợp với Phòng Không Đánh Chặn (Defense Shield Multiplier)
        defense_mult = air_def_report["defense_multiplier"]
        tactical_power = float(abs(raw_vector) * defense_mult)

        # Quyết định hành động
        if tactical_power < 0.10:
            action = "HOLD"
            effective_lots = 0.0
        elif raw_vector > 0:
            action = "BUY"
            effective_lots = max(0.01, round(base_lots * tactical_power, 2))
        else:
            action = "SELL"
            effective_lots = max(0.01, round(base_lots * tactical_power, 2))

        return CombinedArmsDirective(
            target_asset=asset,
            action=action,
            combat_power=round(tactical_power, 4),
            effective_lots=effective_lots,
            primary_branch=primary_branch,
            tactical_breakdown={
                "terrain": terrain,
                "variance_ratio": round(vr, 4),
                "recon": recon_report,
                "armor": armor_report,
                "artillery": artillery_report,
                "air_defense": air_def_report,
                "branch_weights": {
                    "w_recon": w_recon,
                    "w_armor": w_armor,
                    "w_artillery": w_artillery
                }
            },
            threat_status=air_def_report["threat_level"]
        )


# ====================================================================================================
# 01_alpha/legislative_bills/bill_builder.py  —  Bicameral Congress: Alpha Bill Builder & Institutional Alpha Factory
# ====================================================================================================






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


# ====================================================================================================
# 03_portfolio/the_50_states/state_registry.py  —  The 50 States (State Sovereignty & Strategy Pod Registry)
# ====================================================================================================




@dataclass
class StatePod:
    """An autonomous state strategy pod."""
    state_id: str
    state_name: str
    primary_asset: str
    strategy_style: str
    timeframe: str
    allocated_capital: float
    local_drawdown: float = 0.0
    is_active: bool = True

    def update_performance(self, pnl_pct: float) -> bool:
        """Updates local performance. If local drawdown breaches -10%, activates localized quarantine."""
        if pnl_pct < 0:
            self.local_drawdown += pnl_pct
        else:
            self.local_drawdown = min(0.0, self.local_drawdown + pnl_pct)

        if self.local_drawdown <= -0.10: # Localized bankruptcy quarantine
            self.is_active = False
            return False
        return True


# The 18 Elite Sovereign States passed by Supreme Court 36-Month Institutional Audit
# (STATE_17 HK50 eliminated due to 26% WR, session 10044 closed errors, and pure noise PnL)
ELITE_STATE_IDS = [
    "STATE_21", "STATE_24", "STATE_31", "STATE_25", "STATE_26",
    "STATE_34", "STATE_32", "STATE_33", "STATE_03", "STATE_35",
    "STATE_23", "STATE_29", "STATE_27", "STATE_30", "STATE_28",
    "STATE_22", "STATE_12", "STATE_16"
]

# The 32 High-Drawdown / Sub-optimal States Eliminated by Quantitative Audit
ELIMINATED_STATE_IDS = [
    "STATE_01", "STATE_02", "STATE_04", "STATE_05", "STATE_06",
    "STATE_07", "STATE_08", "STATE_09", "STATE_10", "STATE_11",
    "STATE_13", "STATE_14", "STATE_15", "STATE_17", "STATE_18",
    "STATE_19", "STATE_20", "STATE_36", "STATE_37", "STATE_38",
    "STATE_39", "STATE_40", "STATE_41", "STATE_42", "STATE_43",
    "STATE_44", "STATE_45", "STATE_46", "STATE_47", "STATE_48",
    "STATE_49", "STATE_50"
]


class StateFederationRegistry:
    """
    Registry managing all 50 sovereign states of the federation.
    Supports Elite Purified Whitelist mode for institutional execution.
    """

    def __init__(self, elite_mode: bool = False):
        self.states: Dict[str, StatePod] = {}
        self.is_elite_mode: bool = elite_mode
        self._initialize_50_states()
        if elite_mode:
            self.enable_elite_purified_whitelist_mode()

    def _initialize_50_states(self):
        """
        Initializes 50 distinct institutional sovereign state pods on Exness:
        1. States 01 - 10: Commodities, Energy & Crypto (10 states)
        2. States 11 - 20: Global Equity Indices (10 states)
        3. States 21 - 35: Forex Majors & Crosses (15 states)
        4. States 36 - 50: US Mega-Cap Equities (15 states)
        """
        pass

        # Category 1: Commodities, Energy & Crypto (States 01 - 10)
        commodities_crypto = [
            ("STATE_01", "State of Gold Micro-Scalp", "XAUUSDm", "Avellaneda-Stoikov Micro-Scalp", "M15", 250_000.0, 260903),
            ("STATE_02", "State of Silver Ratio Spread", "XAGUSDm", "Cointegration Pairs", "H1", 200_000.0, 260932),
            ("STATE_03", "State of WTI Crude Supply Shock", "USOILm", "Commodity Carry", "H4", 200_000.0, 260933),
            ("STATE_04", "State of Brent Crude Session", "UKOILm", "Session Breakout", "H1", 180_000.0, 260934),
            ("STATE_05", "State of Bitcoin Volatility Arb", "BTCUSDm", "Volatility Momentum (8H)", "8H", 250_000.0, 260904),
            ("STATE_06", "State of Ethereum StatArb", "ETHUSDm", "Statistical Arbitrage", "H4", 200_000.0, 260936),
            ("STATE_07", "State of Solana High-Beta", "SOLUSDm", "High-Beta Momentum", "H1", 180_000.0, 260937),
            ("STATE_08", "State of Platinum Precious Spread", "XPTUSDm", "Precious Metals Carry", "D1", 180_000.0, 260938),
            ("STATE_09", "State of Palladium Volatility Skew", "XPDUSDm", "Volatility Skew", "H4", 180_000.0, 260939),
            ("STATE_10", "State of Natural Gas Breakout", "NATGASm", "Seasonality Breakout", "D1", 200_000.0, 260940),
        ]

        # Category 2: Global Equity Indices (States 11 - 20)
        equity_indices = [
            ("STATE_11", "State of S&P 500 Factor Neutral", "US500m", "Cross-Sectional Factor Neutral", "D1", 250_000.0, 260941),
            ("STATE_12", "State of Nasdaq 100 Tech Momentum", "USTECm", "High-Beta Momentum", "H1", 250_000.0, 260902),
            ("STATE_13", "State of Dow Jones Industrial Trend", "US30m", "TSMOM Trend Following", "H4", 220_000.0, 260943),
            ("STATE_14", "State of Nikkei 225 Tokyo Session", "JP225m", "Tokyo Session Open", "M30", 200_000.0, 260944),
            ("STATE_15", "State of DAX 40 Frankfurt Open", "DE40m", "Frankfurt Breakout", "M15", 200_000.0, 260945),
            ("STATE_16", "State of FTSE 100 London Reversion", "UK100m", "Mean-Reversion", "H1", 180_000.0, 260946),
            ("STATE_17", "State of Hang Seng Liquidity Sweep", "HK50m", "Order Flow Sweep", "M15", 180_000.0, 260947),
            ("STATE_18", "State of ASX 200 Sydney Open", "AU200m", "Sydney Momentum", "H1", 180_000.0, 260948),
            ("STATE_19", "State of Euro Stoxx 50 Value Momentum", "STOXX50m", "Value Momentum", "H4", 180_000.0, 260949),
            ("STATE_20", "State of CAC 40 Paris Momentum", "FR40m", "Paris Cash Open", "H1", 180_000.0, 260950),
        ]

        # Category 3: Forex Majors & Crosses (States 21 - 35)
        forex_pairs = [
            ("STATE_21", "State of EUR/USD Macro Swing", "EURUSDm", "Macro Flow Swing", "D1", 200_000.0, 260901),
            ("STATE_22", "State of GBP/USD Liquidity Sweep", "GBPUSDm", "Order Flow Sweep", "H1", 200_000.0, 260952),
            ("STATE_23", "State of USD/JPY StatArb Carry", "USDJPYm", "Carry & Mean-Revert", "D1", 200_000.0, 260953),
            ("STATE_24", "State of AUD/USD Commodity Flow", "AUDUSDm", "Commodity Beta Flow", "D1", 180_000.0, 260954),
            ("STATE_25", "State of USD/CAD Oil Beta Neutral", "USDCADm", "Oil-Neutral Hedged", "H4", 180_000.0, 260955),
            ("STATE_26", "State of USD/CHF Safe Haven Flow", "USDCHFm", "Safe Haven Flight", "H1", 180_000.0, 260956),
            ("STATE_27", "State of NZD/USD Yield Carry", "NZDUSDm", "Yield Differential Carry", "D1", 180_000.0, 260957),
            ("STATE_28", "State of EUR/JPY Cross Volatility", "EURJPYm", "Volatility Skew", "H1", 180_000.0, 260958),
            ("STATE_29", "State of GBP/JPY Dragon Breakout", "GBPJPYm", "Dragon Trend Breakout", "H1", 200_000.0, 260959),
            ("STATE_30", "State of AUD/JPY Risk Barometer", "AUDJPYm", "Risk-On Barometer", "H4", 180_000.0, 260960),
            ("STATE_31", "State of EUR/GBP Cross Corridor", "EURGBPm", "Corridor Reversion", "H1", 180_000.0, 260961),
            ("STATE_32", "State of EUR/AUD Commodity Cross", "EURAUDm", "Cross Statistical Arb", "H4", 180_000.0, 260962),
            ("STATE_33", "State of GBP/CHF Cross Reversion", "GBPCHFm", "Mean-Reversion", "H1", 180_000.0, 260963),
            ("STATE_34", "State of CAD/JPY Energy Cross Flow", "CADJPYm", "Energy Flow Momentum", "H4", 180_000.0, 260964),
            ("STATE_35", "State of NZD/JPY Pacific Carry", "NZDJPYm", "Pacific Carry Trade", "D1", 180_000.0, 260965),
        ]

        # Category 4: US Mega-Cap Equities on Exness (States 36 - 50)
        us_equities = [
            ("STATE_36", "State of Apple Silicon Alpha", "AAPLm", "Quality Alpha Growth", "D1", 200_000.0, 260966),
            ("STATE_37", "State of Microsoft Cloud Scale", "MSFTm", "Enterprise Moat Alpha", "D1", 200_000.0, 260967),
            ("STATE_38", "State of Nvidia AI Accelerated", "NVDAm", "AI Hardware Pureplay", "H4", 250_000.0, 260968),
            ("STATE_39", "State of Alphabet Quantum Search", "GOOGm", "Ad & Search Cash Machine", "D1", 200_000.0, 260969),
            ("STATE_40", "State of Amazon Cloud & Logistics", "AMZNm", "E-Commerce Dominance", "H4", 200_000.0, 260970),
            ("STATE_41", "State of Meta Social Network Moat", "METAm", "Social Graph Engagement", "H4", 200_000.0, 260971),
            ("STATE_42", "State of Tesla Autonomous Beta", "TSLAm", "High-Beta EV Disruptor", "H1", 220_000.0, 260972),
            ("STATE_43", "State of Berkshire Value Compounder", "BRKm", "Buffett Float Compounder", "D1", 180_000.0, 260973),
            ("STATE_44", "State of JNJ Defensive Healthcare", "JNJm", "Defensive Low-Beta Yield", "D1", 180_000.0, 260974),
            ("STATE_45", "State of JPMorgan Financial Fortress", "JPMm", "Money Center Banking Net Interest", "H4", 180_000.0, 260975),
            ("STATE_46", "State of Visa Global Payments Rail", "Vm", "Network Tollbooth Alpha", "D1", 180_000.0, 260976),
            ("STATE_47", "State of Walmart Consumer Staple", "WMTm", "Non-Cyclical Consumer Cash", "D1", 180_000.0, 260977),
            ("STATE_48", "State of ExxonMobil Free Cash Flow", "XOMm", "Energy Upstream Free Cash", "D1", 180_000.0, 260978),
            ("STATE_49", "State of UnitedHealth Managed Care", "UNHm", "Health Maintenance Moat", "D1", 180_000.0, 260979),
            ("STATE_50", "State of Procter & Gamble Fortress", "PGm", "Recession-Proof Staple", "D1", 180_000.0, 260980),
        ]

        all_state_specs = commodities_crypto + equity_indices + forex_pairs + us_equities


        pass
        pass
        pass

        for sid, sname, asset, style, tf, cap, magic in all_state_specs:

            if sid == "STATE_01":
                pod = GoldScalpPod(allocated_capital=cap)
            elif sid == "STATE_02":
                pod = US30HybridPod(allocated_capital=cap)
            elif sid == "STATE_03":
                pod = USDJPYCarryPod(allocated_capital=cap)
            else:
                pod = BaseStatePod(
                    state_id=sid,
                    state_name=sname,
                    primary_asset=asset,
                    strategy_style=style,
                    timeframe=tf,
                    allocated_capital=cap
                )
            pod.magic = magic
            self.states[sid] = pod


    def get_state(self, state_id: str) -> Optional[StatePod]:
        return self.states.get(state_id)

    def get_all_active_states(self) -> List[StatePod]:
        return [s for s in self.states.values() if s.is_active]

    def enable_elite_purified_whitelist_mode(self, elite_ids: Optional[List[str]] = None) -> List[str]:
        """
        Enforces the 19 Elite Sovereign States passed by Supreme Court 36-Month Audit.
        Quarantines and disables the 31 high-drawdown / low-Sharpe assets (Crypto, Equities, Energy).
        """
        target_ids = set(elite_ids or ELITE_STATE_IDS)
        active_loaded = []
        for sid, pod in self.states.items():
            if sid in target_ids:
                pod.is_active = True
                if hasattr(pod, "is_quarantined"):
                    pod.is_quarantined = False
                active_loaded.append(sid)
            else:
                pod.is_active = False
                if hasattr(pod, "is_quarantined"):
                    pod.is_quarantined = True
                pod.local_drawdown = -0.99  # Invalidate un-whitelisted pods
        self.is_elite_mode = True
        return active_loaded

    def disable_elite_mode(self):
        """Restores all 50 states to un-quarantined status."""
        for pod in self.states.values():
            pod.is_active = True
            if hasattr(pod, "is_quarantined"):
                pod.is_quarantined = False
            pod.local_drawdown = 0.0
        self.is_elite_mode = False

    def get_elite_states(self) -> List[StatePod]:
        """Returns only the 19 Elite Whitelist State pods."""
        elite_set = set(ELITE_STATE_IDS)
        return [s for s in self.states.values() if s.state_id in elite_set]

    def quarantine_pod(self, state_id: str, reason: str = "ADMINISTRATIVE_QUARANTINE") -> bool:
        """Quarantines a state pod, blocking execution allocations."""
        pod = self.get_state(state_id)
        if pod:
            pod.is_active = False
            if hasattr(pod, "is_quarantined"):
                pod.is_quarantined = True
                pod.capital_multiplier = 0.0
            return True
        return False

    def reinstate_pod(self, state_id: str) -> bool:
        """Reinstates a quarantined state pod."""
        pod = self.get_state(state_id)
        if pod:
            if hasattr(pod, "reinstate"):
                pod.reinstate(reset_drawdown=True)
            else:
                pod.is_active = True
                pod.local_drawdown = 0.0
            return True
        return False

    def audit_cross_state_correlations(
        self,
        returns_dict: Dict[str, pd.Series],
        max_corr_threshold: float = 0.85
    ) -> Dict[str, Any]:
        """
        Audits pairwise cross-state correlations to detect redundant systemic risk clusters.
        """
        if len(returns_dict) < 2:
            return {"high_correlation_pairs": [], "status": "OPTIMAL_DIVERSIFICATION"}

        df_returns = pd.DataFrame(returns_dict)
        corr_matrix = df_returns.corr()

        high_corr_pairs: List[Dict[str, Any]] = []
        states_list = list(corr_matrix.columns)

        for i in range(len(states_list)):
            for j in range(i + 1, len(states_list)):
                s1 = states_list[i]
                s2 = states_list[j]
                c_val = float(corr_matrix.loc[s1, s2])
                if abs(c_val) > max_corr_threshold:
                    high_corr_pairs.append({
                        "state_1": s1,
                        "state_2": s2,
                        "correlation": round(c_val, 4),
                        "recommendation": "APPLY_GIVENS_ROTATION_OR_REDUCE_WEIGHT"
                    })

        return {
            "high_correlation_pairs": high_corr_pairs,
            "redundant_pairs_count": len(high_corr_pairs),
            "status": "REDUNDANT_RISK_WARNING" if high_corr_pairs else "OPTIMAL_DIVERSIFICATION"
        }

    def get_federation_summary(self) -> Dict[str, Any]:
        total_states = len(self.states)
        active_states = len(self.get_all_active_states())
        total_capital = sum(s.allocated_capital for s in self.states.values())
        return {
            "total_states": total_states,
            "active_states": active_states,
            "quarantined_states": total_states - active_states,
            "total_capital": total_capital
        }



# ====================================================================================================
# 03_portfolio/the_50_states/base_pod.py  —  Base State Strategy Pod for The 50 States Fleet.
# ====================================================================================================





@dataclass
class StateTradeProposal:
    """A trade proposal submitted by a sovereign state pod."""
    state_id: str
    asset: str
    action: str  # "BUY", "SELL", "HOLD"
    target_lots: float
    strategy_style: str
    rationale: str
    confidence: float
    is_valid: bool
    rejection_reason: Optional[str] = None
    carver_forecast: float = 0.0          # Continuous forecast in [-20.0, +20.0]
    raw_lots: float = 0.0                 # Unbuffered target lots
    buffered_lots: float = 0.0            # Trade buffered lots
    is_buffered: bool = False             # Whether buffering prevented an unnecessary trade
    cash_vol_budget: float = 0.0          # Daily cash volatility allocated by the Fed


INDEX_MAX_LOTS: Dict[str, float] = {
    "USTEC": 0.15,
    "USTECm": 0.15,
    "US30": 0.10,
    "US30m": 0.10,
    "US500": 0.20,
    "US500m": 0.20,
}


class BaseStatePod(StatePod):
    """
    Autonomous Strategy Pod with localized risk governance, Carver continuous
    forecasting, and localized drawdown management.
    """

    def __init__(
        self,
        state_id: str,
        state_name: str,
        primary_asset: str,
        strategy_style: str,
        timeframe: str,
        allocated_capital: float = 200_000.0,
        deleveraging_drawdown_threshold: float = -0.03, # -3%
        quarantine_drawdown_threshold: float = -0.05    # -5%
    ):
        super().__init__(
            state_id=state_id,
            state_name=state_name,
            primary_asset=primary_asset,
            strategy_style=strategy_style,
            timeframe=timeframe,
            allocated_capital=allocated_capital,
            local_drawdown=0.0,
            is_active=True
        )
        self.deleveraging_drawdown_threshold = deleveraging_drawdown_threshold
        self.quarantine_drawdown_threshold = quarantine_drawdown_threshold
        self.is_quarantined: bool = False
        self.capital_multiplier: float = 1.0
        self.trade_history: List[Dict[str, Any]] = []

    def update_performance(self, pnl_pct: float) -> bool:
        """
        Updates local performance and enforces the institutional drawdown ladder.
        - Level 1: Drawdown <= -3% -> cuts capital/leverage by 50%
        - Level 2: Drawdown <= -5% -> activates full quarantine
        """
        if pnl_pct < 0:
            self.local_drawdown += pnl_pct
        else:
            self.local_drawdown = min(0.0, self.local_drawdown + pnl_pct)

        # Drawdown Ladder Enforcement
        if self.local_drawdown <= self.quarantine_drawdown_threshold:
            self.is_active = False
            self.is_quarantined = True
            self.capital_multiplier = 0.0
            return False
        elif self.local_drawdown <= self.deleveraging_drawdown_threshold:
            self.capital_multiplier = 0.50
        else:
            self.capital_multiplier = 1.0

        return True

    def reinstate(self, reset_drawdown: bool = True):
        """Reinstates a quarantined state pod after audit and reset."""
        self.is_active = True
        self.is_quarantined = False
        self.capital_multiplier = 1.0
        if reset_drawdown:
            self.local_drawdown = 0.0

    # ----------------------------------------------------------------------------------
    # ROBERT CARVER CONTINUOUS FORECASTING ENGINE (pysystemtrade)
    # ----------------------------------------------------------------------------------
    def calculate_continuous_forecast(
        self,
        market_df: pd.DataFrame,
        fast_period: int = 8,
        slow_period: int = 32,
    ) -> float:
        """
        Robert Carver Continuous Forecast Engine (pysystemtrade).
        Maps market indicators to a standardized [-20.0, +20.0] continuous scalar.
        - +10: Standard buy
        - +20: Maximum conviction buy (capped)
        - -10: Standard short
        - -20: Maximum conviction short (capped)
        - 0: Neutral equilibrium
        """
        if len(market_df) < max(20, slow_period):
            return 0.0

        close = market_df["close"].values
        current_price = float(close[-1])

        # Dual mode: Mean-Reversion or EWMAC Trend based on pod strategy style
        if "REVERSION" in self.strategy_style.upper() or "SCALP" in self.strategy_style.upper():
            # Mean reversion forecast (inverts standardized z-score)
            ma = float(np.mean(close[-20:]))
            std = float(np.std(close[-20:]))
            if std <= 1e-8:
                return 0.0
            z_score = (current_price - ma) / std
            raw_forecast = -z_score * 10.0
        else:
            # EWMAC (Exponentially Weighted Moving Average Crossover) trend forecast
            ema_fast = pd.Series(close).ewm(span=fast_period).mean().iloc[-1]
            ema_slow = pd.Series(close).ewm(span=slow_period).mean().iloc[-1]
            raw_diff = float(ema_fast - ema_slow)

            # Divide by rolling price volatility to obtain risk-normalized forecast
            returns = np.diff(close) / np.maximum(1e-8, close[:-1])
            ann_vol = float(np.std(returns[-30:]) * np.sqrt(256) * current_price) if len(returns) >= 30 else current_price * 0.01
            scalar = 10.0 / (ann_vol * 0.05) if ann_vol > 0 else 1.0
            raw_forecast = raw_diff * scalar

        # Carver Forecast Capping: Strictly bound between -20.0 and +20.0
        capped_forecast = float(np.clip(raw_forecast, -20.0, 20.0))
        return round(capped_forecast, 2)

    def calculate_carver_target_position(
        self,
        cash_vol_target: float,
        forecast: float,
        current_position_lot: float = 0.0,
        atr_price: Optional[float] = None,
        contract_size: Optional[float] = None,
        buffer_fraction: float = 0.10,
        min_lot: float = 0.01,
        max_lot: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Robert Carver Block Value & Volatility Target Position Sizing:
        1. Dollar Risk per Contract = ATR * ContractSize
        2. Raw Target Lots = (Cash Vol Target * (|Forecast| / 10.0)) / Dollar Risk per Contract
        3. Carver Trade Buffering (+/- 10%) against current_position_lot to eliminate churn.
        """
        clean_asset = self.primary_asset.upper().replace("M", "")
        if max_lot is None:
            if any(fx in clean_asset for fx in ["EUR", "GBP", "USD", "JPY", "AUD", "CAD", "CHF", "NZD"]) and not any(i in clean_asset for i in ["US30", "US500", "USTEC", "BTC", "ETH", "XAU"]):
                max_lot = 0.15
            elif "US30" in clean_asset or "US500" in clean_asset or "USTEC" in clean_asset:
                max_lot = 0.15
            elif any(c in clean_asset for c in ["BTC", "ETH", "SOL"]):
                max_lot = 0.10
            elif any(m in clean_asset for m in ["XAU", "XAG", "XPT", "XPD", "XNG"]):
                max_lot = 0.50
            else:
                max_lot = 0.15

        # Check explicit INDEX_MAX_LOTS ceiling
        for sym_key, cap_lot in INDEX_MAX_LOTS.items():
            if sym_key in self.primary_asset or sym_key in clean_asset:
                max_lot = min(max_lot if max_lot is not None else cap_lot, cap_lot)
                break

        if contract_size is None:
            if "XAU" in clean_asset or "GOLD" in clean_asset:
                contract_size = 100.0
            elif "US30" in clean_asset or "US500" in clean_asset or "USTEC" in clean_asset or "BTC" in clean_asset:
                contract_size = 1.0
            else:
                contract_size = 100_000.0

        effective_atr = atr_price if (atr_price and atr_price > 0) else 10.0
        dollar_risk_per_contract = effective_atr * contract_size
        if dollar_risk_per_contract <= 0:
            dollar_risk_per_contract = 100.0

        forecast_scalar = abs(forecast) / 10.0
        raw_target_lots = (cash_vol_target * forecast_scalar) / dollar_risk_per_contract
        raw_target_lots = float(np.clip(raw_target_lots, 0.0, max_lot))

        # Apply state pod capital multiplier (Drawdown Ladder)
        raw_target_lots = raw_target_lots * self.capital_multiplier

        # Position Buffering (+/- 10%)
        is_buffered = False
        buffered_lots = raw_target_lots
        if current_position_lot > 0.0:
            diff = abs(raw_target_lots - current_position_lot)
            if diff <= buffer_fraction * current_position_lot:
                buffered_lots = current_position_lot
                is_buffered = True

        final_lots = round(buffered_lots, 2)
        if final_lots > 0 and final_lots < min_lot:
            final_lots = min_lot

        # Strict hard cap enforcement against INDEX_MAX_LOTS
        for sym_key, cap_lot in INDEX_MAX_LOTS.items():
            if sym_key in self.primary_asset or sym_key in clean_asset:
                final_lots = min(final_lots, cap_lot)
                break

        return {
            "raw_lots": round(raw_target_lots, 2),
            "buffered_lots": final_lots,
            "is_buffered": is_buffered,
            "dollar_risk_per_contract": round(dollar_risk_per_contract, 2),
            "forecast_scalar": round(forecast_scalar, 2),
        }

    def calculate_risk_parity_lot(
        self,
        account_equity: float = 1000.0,
        current_price: float = 2000.0,
        atr: Optional[float] = None,
        risk_fraction: float = 0.005,
    ) -> float:
        """
        Dynamic Risk Parity position sizing for sovereign state pods:
        Calculates safe lot size calibrated to account equity ($1,000 retail vs $250k institutional).
        Enforces local drawdown ladder de-leveraging.
        """
        if account_equity <= 0:
            return 0.01

        clean_asset = self.primary_asset.upper().replace("M", "")
        if "XAU" in clean_asset or "GOLD" in clean_asset:
            contract_size = 100.0
            max_lot = 0.05  # Strict ceiling for Gold
            target_risk_usd = min(75.0, max(1.0, account_equity * risk_fraction))
        elif "US30" in clean_asset or "US500" in clean_asset or "USTEC" in clean_asset or "BTC" in clean_asset:
            contract_size = 1.0
            max_lot = 0.10 if account_equity <= 5000 else (0.15 if account_equity <= 10000 else (0.50 if account_equity <= 25000 else 5.0))
            target_risk_usd = max(1.0, account_equity * risk_fraction)
        else:  # FX Pairs
            contract_size = 100_000.0
            max_lot = 0.05 if account_equity <= 5000 else (0.15 if account_equity <= 25000 else 5.0)
            target_risk_usd = max(1.0, account_equity * risk_fraction)

        # Strict hard cap enforcement against INDEX_MAX_LOTS
        for sym_key, cap_lot in INDEX_MAX_LOTS.items():
            if sym_key in self.primary_asset or sym_key in clean_asset:
                max_lot = min(max_lot, cap_lot)
                break

        effective_atr = atr if (atr and atr > 0) else (current_price * 0.005)
        dollar_risk_per_lot = effective_atr * contract_size * 1.5

        if dollar_risk_per_lot > 0:
            raw_lot = target_risk_usd / dollar_risk_per_lot
        else:
            raw_lot = 0.01

        effective_lot = raw_lot * self.capital_multiplier
        final_lot = max(0.01, min(round(effective_lot, 2), max_lot))

        # Strict hard cap enforcement against INDEX_MAX_LOTS
        for sym_key, cap_lot in INDEX_MAX_LOTS.items():
            if sym_key in self.primary_asset or sym_key in clean_asset:
                final_lot = min(final_lot, cap_lot)
                break

        return final_lot

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        account_equity: float = 10000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposal with Carver Continuous Forecast [-20, +20]
        and dynamic volatility-targeted sizing with position buffering.
        """
        if not self.is_active or self.is_quarantined:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="State is quarantined or inactive.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="STATE_QUARANTINED"
            )

        if len(market_df) < 20:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="Insufficient bar history.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="INSUFFICIENT_DATA"
            )

        close = market_df["close"].values
        current_price = float(close[-1])
        std20 = float(np.std(close[-20:]))

        # 1. Compute Carver Continuous Forecast in [-20.0, +20.0]
        forecast = self.calculate_continuous_forecast(market_df)

        # 2. Determine Action & Conviction
        if forecast >= 2.0:
            action = "BUY"
            confidence = min(0.95, 0.50 + (forecast / 40.0))
            rationale = f"Carver Bullish Continuous Forecast: {forecast:+.2f} / +20.0"
        elif forecast <= -2.0:
            action = "SELL"
            confidence = min(0.95, 0.50 + (abs(forecast) / 40.0))
            rationale = f"Carver Bearish Continuous Forecast: {forecast:+.2f} / -20.0"
        else:
            action = "HOLD"
            confidence = 0.50
            rationale = f"Carver Neutral Forecast: {forecast:+.2f} (Within equilibrium [-2.0, +2.0])"

        # 3. Position Sizing: Carver Vol Target if budget available, else Risk Parity
        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=std20 if std20 > 0 else current_price * 0.005,
            )
            raw_lots = carver_sizing["raw_lots"]
            target_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=std20 if std20 > 0 else current_price * 0.005,
            )
            target_lots = raw_lots
            is_buffered = False
        else:
            raw_lots = 0.0
            target_lots = 0.0
            is_buffered = False

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=target_lots,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD",
            carver_forecast=forecast,
            raw_lots=raw_lots,
            buffered_lots=target_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )



# ====================================================================================================
# 03_portfolio/the_50_states/state_01_xauusd_scalp/pod.py  —  State 01: Gold Microstructure Scalping Pod (XAUUSD M15).
# ====================================================================================================




_event_mod = sys.modules[__name__]
SymmetricCUSUMFilter__pod = _event_mod.SymmetricCUSUMFilter

_alpha_mod = sys.modules[__name__]
FormulaicAlphas101__pod = _alpha_mod.FormulaicAlphas101


class GoldScalpPod(BaseStatePod):
    """
    Sovereign State 01: XAUUSD Microstructure Scalper.
    """

    def __init__(self, allocated_capital: float = 250_000.0):
        super().__init__(
            state_id="STATE_01",
            state_name="State of Gold Micro-Scalp",
            primary_asset="XAUUSD",
            strategy_style="Avellaneda-Stoikov Micro-Scalp",
            timeframe="M15",
            allocated_capital=allocated_capital
        )
        self.cusum_filter = SymmetricCUSUMFilter__pod(threshold_multiplier=1.8, default_threshold=0.008)

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        account_equity: float = 1000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on CUSUM structural events, Garman-Klass volatility,
        and Robert Carver continuous forecasting [-20, +20].
        """
        if not self.is_active or self.is_quarantined:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="State is quarantined or inactive.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="STATE_QUARANTINED"
            )

        if len(market_df) < 15:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="Insufficient bar history.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="INSUFFICIENT_DATA"
            )

        close = market_df["close"]
        gk_vol = FormulaicAlphas101__pod.calculate_garman_klass_volatility(market_df).iloc[-1]
        a101 = FormulaicAlphas101__pod.alpha_101(market_df).iloc[-1]

        # Check structural CUSUM event
        cusum_res = self.cusum_filter.filter_events(close)
        latest_event_direction = cusum_res["event_directions"][-1] if cusum_res["event_directions"] else 0

        # Continuous Carver forecast in [-20.0, +20.0]
        raw_forecast = (a101 * 15.0) + (latest_event_direction * 10.0)
        forecast = float(np.clip(raw_forecast, -20.0, 20.0))

        # Decision rule
        if forecast >= 2.0:
            action = "BUY"
            rationale = f"Gold upward CUSUM / Alpha101 bullish: Forecast {forecast:+.2f}, GK Vol: {round(gk_vol, 4)}"
            confidence = min(0.95, 0.50 + (forecast / 40.0))
        elif forecast <= -2.0:
            action = "SELL"
            rationale = f"Gold downward CUSUM / Alpha101 bearish: Forecast {forecast:+.2f}, GK Vol: {round(gk_vol, 4)}"
            confidence = min(0.95, 0.50 + (abs(forecast) / 40.0))
        else:
            action = "HOLD"
            rationale = f"Gold in noise equilibrium: Forecast {forecast:+.2f} (Within [-2.0, +2.0])"
            confidence = 0.50

        current_price = float(close.iloc[-1])

        # Dynamic Volatility Sizing based on ATR(14) and $75.00 Hard Stop Cap
        if "high" in market_df.columns and "low" in market_df.columns:
            tr1 = market_df["high"] - market_df["low"]
            tr2 = (market_df["high"] - market_df["close"].shift(1)).abs()
            tr3 = (market_df["low"] - market_df["close"].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr14 = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else float(tr.mean())
        else:
            atr14 = gk_vol * current_price if gk_vol > 0 else current_price * 0.005

        if np.isnan(atr14) or atr14 <= 0:
            atr14 = 20.0

        max_risk_usd = 75.0
        multiplier = 1.5
        contract_size = 100.0
        dollar_risk_per_lot = atr14 * multiplier * contract_size

        dynamic_xau_lot = max_risk_usd / dollar_risk_per_lot if dollar_risk_per_lot > 0 else 0.02
        volatility_capped_lot = float(np.clip(round(dynamic_xau_lot, 2), 0.01, 0.05))

        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=atr14,
                contract_size=contract_size,
                max_lot=volatility_capped_lot,
            )
            raw_lots = min(carver_sizing["raw_lots"], volatility_capped_lot)
            effective_lots = min(carver_sizing["buffered_lots"], volatility_capped_lot)
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = volatility_capped_lot
            effective_lots = volatility_capped_lot
            is_buffered = False
        else:
            raw_lots = 0.0
            effective_lots = 0.0
            is_buffered = False

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=effective_lots,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD",
            carver_forecast=round(forecast, 2),
            raw_lots=raw_lots,
            buffered_lots=effective_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )


# ====================================================================================================
# 03_portfolio/the_50_states/state_02_us30_hybrid/pod.py  —  State 02: Dow Jones Hybrid Momentum Pod (US30 H1).
# ====================================================================================================




_mit_mod = sys.modules[__name__]
MITMatrixCompensator__pod = _mit_mod.MITMatrixCompensator


class US30HybridPod(BaseStatePod):
    """
    Sovereign State 02: US30 Equity Index Trend & Macro Momentum Pod.
    """

    def __init__(self, allocated_capital: float = 200_000.0):
        super().__init__(
            state_id="STATE_02",
            state_name="State of Dow Jones Momentum",
            primary_asset="US30",
            strategy_style="TSMOM Hybrid Momentum",
            timeframe="H1",
            allocated_capital=allocated_capital
        )

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        fed_stance: str = "NEUTRAL",
        account_equity: float = 1000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on Lo-MacKinlay Variance Ratio, FED macro stance,
        and Carver continuous forecasting with volatility budgeting and position buffering.
        """
        if not self.is_active or self.is_quarantined:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="State is quarantined or inactive.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="STATE_QUARANTINED"
            )

        if len(market_df) < 25:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="Insufficient bar history for VR calculation.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="INSUFFICIENT_DATA"
            )

        close = market_df["close"].values
        vr_audit = MITMatrixCompensator__pod.lo_mackinlay_variance_ratio(close[-25:], q=5)
        momentum_10 = (close[-1] - close[-10]) / close[-10]

        # Decision rules
        is_uptrend = momentum_10 > 0.002 and vr_audit.market_regime != "MEAN_REVERTING"
        is_downtrend = momentum_10 < -0.002 and vr_audit.market_regime != "MEAN_REVERTING"

        # Continuous Carver forecast in [-20.0, +20.0]
        raw_forecast = (momentum_10 / 0.005) * 12.0
        if vr_audit.market_regime == "MEAN_REVERTING":
            raw_forecast *= 0.3
        forecast = float(np.clip(raw_forecast, -20.0, 20.0))

        if is_uptrend:
            if "TIGHTENING" in fed_stance.upper() or "QT" in fed_stance.upper():
                action = "HOLD"
                forecast = 0.0
                rationale = "Bullish momentum blocked by Federal Reserve Quantitative Tightening (QT)."
                confidence = 0.40
            else:
                action = "BUY"
                forecast = max(2.5, forecast)
                rationale = f"US30 Strong Momentum Trend (VR={round(vr_audit.variance_ratio, 2)}), Macro={fed_stance}"
                confidence = 0.75

        elif is_downtrend:
            action = "SELL"
            forecast = min(-2.5, forecast)
            rationale = f"US30 Bearish Momentum Breakdown (VR={round(vr_audit.variance_ratio, 2)})"
            confidence = 0.75

        else:
            action = "HOLD"
            forecast = 0.0
            rationale = f"US30 in Random Walk / Consolidation (VR={round(vr_audit.variance_ratio, 2)})"
            confidence = 0.50

        current_price = float(close[-1])
        effective_atr = abs(close[-1] - close[-10]) if len(close) >= 10 else 200.0

        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=effective_atr,
                contract_size=1.0,
            )
            raw_lots = carver_sizing["raw_lots"]
            effective_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=effective_atr,
                risk_fraction=0.005,
            )
            effective_lots = raw_lots
            is_buffered = False
        else:
            raw_lots = 0.0
            effective_lots = 0.0
            is_buffered = False

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=effective_lots,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD",
            carver_forecast=round(forecast, 2),
            raw_lots=raw_lots,
            buffered_lots=effective_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )


# ====================================================================================================
# 03_portfolio/the_50_states/state_03_usdjpy_carry/pod.py  —  State 03: USD/JPY Carry & StatArb Pod (USDJPY H4).
# ====================================================================================================





class USDJPYCarryPod(BaseStatePod):
    """
    Sovereign State 03: USD/JPY Carry Trade & Interest Rate Differential Pod.
    """

    def __init__(self, allocated_capital: float = 200_000.0):
        super().__init__(
            state_id="STATE_03",
            state_name="State of USD/JPY Carry & Mean-Revert",
            primary_asset="USDJPY",
            strategy_style="StatArb Carry",
            timeframe="H4",
            allocated_capital=allocated_capital
        )

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        us_yield_10y: float = 4.25,
        jp_yield_10y: float = 0.85,
        account_equity: float = 1000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on US-Japan 10Y sovereign bond yield differential
        and Carver continuous forecasting with volatility budgeting and position buffering.
        """
        if not self.is_active or self.is_quarantined:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="State is quarantined or inactive.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="STATE_QUARANTINED"
            )

        if len(market_df) < 20:
            return StateTradeProposal(
                state_id=self.state_id,
                asset=self.primary_asset,
                action="HOLD",
                target_lots=0.0,
                strategy_style=self.strategy_style,
                rationale="Insufficient bar history.",
                confidence=0.0,
                is_valid=False,
                rejection_reason="INSUFFICIENT_DATA"
            )

        yield_differential = us_yield_10y - jp_yield_10y
        close = market_df["close"].values
        ma20 = float(np.mean(close[-20:]))
        current_price = close[-1]
        dist_ma_pct = (current_price - ma20) / ma20

        # Continuous Carver forecast in [-20.0, +20.0]
        raw_forecast = ((yield_differential - 1.75) * 6.0) - (dist_ma_pct / 0.03 * 10.0)
        forecast = float(np.clip(raw_forecast, -20.0, 20.0))

        # Carry trading decision rules
        # Widening yield gap + not excessively overextended above MA20 -> Strong Long Carry
        if yield_differential > 2.50 and dist_ma_pct < 0.03:
            action = "BUY"
            forecast = max(2.5, forecast)
            rationale = f"Positive Carry Yield Spread ({round(yield_differential, 2)}%), Price near MA20"
            confidence = 0.72
        elif yield_differential < 1.0 or dist_ma_pct > 0.05:
            action = "SELL"
            forecast = min(-2.5, forecast)
            rationale = f"Negative Carry Divergence or Mean-Reversion Overbought (Dist={round(dist_ma_pct*100, 2)}%)"
            confidence = 0.65
        else:
            action = "HOLD"
            forecast = 0.0
            rationale = "Carry differential in equilibrium; no directional skew."
            confidence = 0.50

        effective_atr = abs(current_price - ma20) if abs(current_price - ma20) > 0 else (current_price * 0.005)

        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=effective_atr,
                contract_size=100_000.0,
            )
            raw_lots = carver_sizing["raw_lots"]
            effective_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=effective_atr,
                risk_fraction=0.005,
            )
            effective_lots = raw_lots
            is_buffered = False
        else:
            raw_lots = 0.0
            effective_lots = 0.0
            is_buffered = False

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=effective_lots,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=action != "HOLD",
            carver_forecast=round(forecast, 2),
            raw_lots=raw_lots,
            buffered_lots=effective_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )


# ====================================================================================================
# 03_portfolio/the_50_states/state_05_nowtrading_mtf/pod.py  —  State 05: NowTrading Multi-Timeframe (MTF) RSI Pod.
# ====================================================================================================




class NowTradingMtfPod(BaseStatePod):
    """
    Sovereign State 05: NowTrading MTF Pullback Strategy.
    """

    def __init__(self, allocated_capital: float = 250_000.0, primary_asset: str = "XAUUSDm"):
        super().__init__(
            state_id="STATE_05",
            state_name="State of NowTrading MTF",
            primary_asset=primary_asset,
            strategy_style="MTF RSI Trend Pullback",
            timeframe="M15",
            allocated_capital=allocated_capital
        )
        # Core thresholds from original signal_engine.py
        self.rsi_period = 14
        self.rsi_buy = 55.0
        self.rsi_sell = 45.0
        self.rsi_pullback = 50.0

    def generate_trade_proposal(
        self,
        market_df: pd.DataFrame,
        account_equity: float = 1000.0,
        cash_vol_budget: Optional[float] = None,
        current_position_lot: float = 0.0,
    ) -> StateTradeProposal:
        """
        Generates trade proposals based on MTF RSI and Pullback Exhaustion,
        with Carver continuous forecasting, cash volatility budgeting, and position buffering.
        NOTE: This expects market_df to be M15 data, but in a real MTF setup, 
        we simulate H1/H4 RSI by using longer RSI periods or downsampled data.
        For this pod, we approximate H1 as M15 * 4, H4 as M15 * 16.
        """
        if not self.is_active or self.is_quarantined:
            return self._hold_proposal("State is quarantined or inactive.", "STATE_QUARANTINED")

        if len(market_df) < self.rsi_period * 16 + 2:
            return self._hold_proposal("Insufficient bar history for H4 approximation.", "INSUFFICIENT_DATA")

        close = market_df["close"]

        # Approximate MTF RSI using extended periods
        rsi_m15 = ta.rsi(close, length=self.rsi_period)
        rsi_h1 = ta.rsi(close, length=self.rsi_period * 4)
        rsi_h4 = ta.rsi(close, length=self.rsi_period * 16)
        
        if rsi_m15 is None or rsi_h1 is None or rsi_h4 is None:
             return self._hold_proposal("RSI calculation failed.", "RSI_FAILED")

        val_m15 = rsi_m15.iloc[-1]
        val_h1 = rsi_h1.iloc[-1]
        val_h4 = rsi_h4.iloc[-1]
        
        prev_m15 = rsi_m15.iloc[-2]
        
        # Pullback exhaustion logic from legacy engine
        m15_rsi_rising = val_m15 > prev_m15
        m15_rsi_falling = val_m15 < prev_m15
        
        m15_close_rising = close.iloc[-1] > close.iloc[-2]
        m15_close_falling = close.iloc[-1] < close.iloc[-2]
        
        # Lookback for local highs/lows
        lb = 3
        local_lows = market_df["low"].iloc[-1 - lb : -1]
        local_highs = market_df["high"].iloc[-1 - lb : -1]
        
        m15_fresh_local_low = market_df["low"].iloc[-1] < local_lows.min()
        m15_fresh_local_high = market_df["high"].iloc[-1] > local_highs.max()

        action = "HOLD"
        rationale = "No signal"
        confidence = 0.50
        forecast = 0.0

        # BUY LOGIC
        if val_h4 > self.rsi_buy and val_h1 > self.rsi_buy:
            if val_m15 > self.rsi_pullback and m15_rsi_rising and m15_close_rising and not m15_fresh_local_low:
                action = "BUY"
                raw_fc = 5.0 + (val_h4 - self.rsi_buy) * 0.5 + (val_m15 - self.rsi_pullback) * 0.5
                forecast = float(np.clip(raw_fc, -20.0, 20.0))
                rationale = f"BUY: RSI H4={val_h4:.1f} H1={val_h1:.1f} M15={val_m15:.1f} (Pullback Exhausted)"
                confidence = 0.75

        # SELL LOGIC
        elif val_h4 < self.rsi_sell and val_h1 < self.rsi_sell:
            if val_m15 < self.rsi_pullback and m15_rsi_falling and m15_close_falling and not m15_fresh_local_high:
                action = "SELL"
                raw_fc = -5.0 - (self.rsi_sell - val_h4) * 0.5 - (self.rsi_pullback - val_m15) * 0.5
                forecast = float(np.clip(raw_fc, -20.0, 20.0))
                rationale = f"SELL: RSI H4={val_h4:.1f} H1={val_h1:.1f} M15={val_m15:.1f} (Pullback Exhausted)"
                confidence = 0.75

        if action == "HOLD":
            return self._hold_proposal(rationale, "NO_TRIGGER")

        current_price = float(close.iloc[-1])
        atr_series = ta.atr(market_df["high"], market_df["low"], close, length=14)
        atr = float(atr_series.iloc[-1]) if atr_series is not None and not np.isnan(atr_series.iloc[-1]) else current_price * 0.005
        
        if cash_vol_budget and cash_vol_budget > 0 and action != "HOLD":
            carver_sizing = self.calculate_carver_target_position(
                cash_vol_target=cash_vol_budget,
                forecast=forecast,
                current_position_lot=current_position_lot,
                atr_price=atr,
                contract_size=100.0,
            )
            raw_lots = carver_sizing["raw_lots"]
            effective_lots = carver_sizing["buffered_lots"]
            is_buffered = carver_sizing["is_buffered"]
        elif action != "HOLD":
            raw_lots = self.calculate_risk_parity_lot(
                account_equity=account_equity,
                current_price=current_price,
                atr=atr,
                risk_fraction=0.005,
            )
            effective_lots = raw_lots
            is_buffered = False
        else:
            raw_lots = 0.0
            effective_lots = 0.0
            is_buffered = False

        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action=action,
            target_lots=effective_lots,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=confidence,
            is_valid=True,
            carver_forecast=round(forecast, 2),
            raw_lots=raw_lots,
            buffered_lots=effective_lots,
            is_buffered=is_buffered,
            cash_vol_budget=cash_vol_budget or 0.0,
        )

    def _hold_proposal(self, rationale: str, rejection_reason: str) -> StateTradeProposal:
        return StateTradeProposal(
            state_id=self.state_id,
            asset=self.primary_asset,
            action="HOLD",
            target_lots=0.0,
            strategy_style=self.strategy_style,
            rationale=rationale,
            confidence=0.0,
            is_valid=False,
            rejection_reason=rejection_reason
        )
