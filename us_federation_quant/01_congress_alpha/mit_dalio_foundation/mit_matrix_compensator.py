"""
Viện Nghiên Cứu Chiến Lược MIT — Thuật Toán Bù & Matrix Chiến Lược Hedge.
Dựa trên nền tảng toán học hàn lâm MIT:
1. Gilbert Strang (MIT 18.065): Chiếu Trực Giao Không Gian Không (Left Nullspace Projection).
   M = I - B(B^T B)^-1 B^T -> Triệt tiêu 100% rủi ro hệ thống: B^T @ w* = 0.
2. Thuật Toán Bù Rủi Ro Nhân Tố (Factor Compensation Algorithm):
   Tính toán chính xác vector bù đắp (hedge overlay vector):
   w_hedge = - B(B^T B)^-1 @ (B^T @ w_raw), đảm bảo w_raw + w_hedge = w*.
3. Peter Kempthorne (MIT 18.642): Ma Trận Xoay Givens Khử Tương Quan Cặp (Givens Rotation).
   Đường chéo hóa ma trận hiệp phương sai 2x2 để triệt tiêu covariance giữa 2 tài sản tương quan mạnh.
4. Andrew W. Lo (MIT Sloan): Kiểm Định Tỷ Số Phương Sai Lo-MacKinlay (1988) VR(q).
   Chẩn đoán regime thị trường vững chắc với sai số chuẩn chống phương sai thay đổi (Heteroskedasticity-robust).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats


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
