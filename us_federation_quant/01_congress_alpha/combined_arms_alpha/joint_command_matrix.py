"""
BỘ TỔNG THAM MƯU TÁC CHIẾN HỢP THÀNH (COMBINED ARMS JOINT COMMAND MATRIX)
Hợp nhất 4 Binh chủng thành một cỗ máy chiến tranh định lượng bất khả chiến bại:
1. Trinh sát (Reconnaissance)
2. Thiết giáp (Armored Momentum)
3. Pháo binh (Artillery Mean Reversion)
4. Phòng không (Air Defense Volatility)

Nguyên lý Tác chiến:
- Địa hình Xu hướng (Trending) -> Thiết giáp làm mũi nhọn đột kích.
- Địa hình Đi ngang (Ranging)  -> Pháo binh dập đạn chế áp hai đầu.
- Gặp Bão tố (High Volatility)-> Phòng không bật Vòm Sắt, siết chặt kỷ luật sinh tồn.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from .recon_signals import ReconnaissanceUnit
from .armored_momentum import ArmoredMomentumUnit
from .artillery_mean_reversion import ArtilleryMeanReversionUnit
from .air_defense_volatility import AirDefenseVolatilityUnit
from ..senate_macro.macro_regime import lo_mackinlay_variance_ratio


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
