"""
Toán Tử Sai Phân Phân Số (Fractional Differentiation - FracDiff Engine).
Dựa trên Marcos López de Prado, 'Advances in Financial Machine Learning' (Chương 5).

Nguyên Lý Cốt Lõi:
- Sai phân nguyên thông thường (d=1, log returns) tiêu diệt 90-95% trí nhớ chuỗi thời gian,
  làm triệt tiêu khả năng dự báo dài hạn của các mô hình học máy.
- Sai phân phân số với bậc không nguyên d in [0, 1] cho phép đạt tính dừng (ADF test p < 0.05)
  trong khi vẫn bảo toàn trên 80% tương quan và cấu trúc hỗ trợ/kháng cự/chu kỳ của giá gốc.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


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
