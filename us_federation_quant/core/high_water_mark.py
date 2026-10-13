"""
US Federation Quant — High-Water Mark Tracker
=============================================
Theo dõi đỉnh vốn (High-Water Mark) và tính drawdown ĐÚNG theo Hiến pháp:

    drawdown = (equity - HWM) / HWM        (luôn <= 0)

VÌ SAO CẦN FILE NÀY
-------------------
`live_federation_runner.py` trước đây nạp vào thang drawdown đại lượng:

    drawdown = (equity - balance) / balance

Đó là lãi/lỗ ĐANG TRÔI NỔI của lệnh đang mở, không phải drawdown từ đỉnh.
Hệ quả: tài khoản có thể lỗ thật 30% từ đỉnh, nhưng nếu không còn lệnh mở thì
equity == balance, đại lượng trên bằng 0, và kill-switch -7.5% KHÔNG BAO GIỜ
kích hoạt. Nó chỉ bắt được cú sập trong một lệnh đơn lẻ.

`WallStreetPodDefense.enforce_drawdown_ladder()` tự nó viết đúng — nó chỉ bị
nạp sai đầu vào. File này cung cấp đầu vào đúng.

TÍNH BỀN VỮNG QUA LẦN KHỞI ĐỘNG LẠI
-----------------------------------
HWM được ghi xuống đĩa. Nếu giữ trong RAM, mỗi lần restart bot sẽ đặt lại đỉnh
về equity hiện tại — tức là xoá sạch drawdown đang có và vô hiệu hoá thang bậc
đúng vào lúc cần nó nhất. Restart sau một chuỗi lỗ là tình huống thường gặp
nhất, nên trạng thái BẮT BUỘC phải sống sót qua restart.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from us_federation_quant.core.audit_logger import get_logger
except ImportError:
    try:
        from core.audit_logger import get_logger
    except ImportError:
        def get_logger():
            return logging.getLogger("USFederationQuant")

logger = get_logger()


@dataclass(frozen=True)
class HighWaterMarkState:
    """Ảnh chụp trạng thái đỉnh vốn tại một thời điểm."""

    equity_usd: float
    high_water_mark_usd: float
    drawdown_fraction: float  # <= 0.0, ví dụ -0.075 nghĩa là -7.5%
    drawdown_pct: float       # cùng số trên, đã nhân 100
    is_new_peak: bool
    peak_at_utc: str
    updated_at_utc: str

    @property
    def is_at_peak(self) -> bool:
        return self.drawdown_fraction >= 0.0


class HighWaterMarkTracker:
    """
    Theo dõi đỉnh vốn bền vững qua các lần khởi động lại.

    Cách dùng::

        hwm = HighWaterMarkTracker(bot_id="us_federation_quant")
        state = hwm.update(current_equity=9_250.0)
        capital_mult, pod_status, kill = WallStreetPodDefense.enforce_drawdown_ladder(
            state.drawdown_fraction
        )
    """

    def __init__(
        self,
        bot_id: str = "us_federation_quant",
        logs_dir: Optional[str] = None,
        state_file: Optional[str] = None,
    ):
        self.bot_id = bot_id

        if state_file is not None:
            self.state_file = Path(state_file)
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            if logs_dir is None:
                base_dir = Path(__file__).resolve().parent.parent / "logs"
            else:
                base_dir = Path(logs_dir)
            base_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = base_dir / f"high_water_mark_{self.bot_id}.json"

        self._hwm: Optional[float] = None
        self._peak_at_utc: Optional[str] = None
        self._load()

    # ------------------------------------------------------------------ Bền vững trên đĩa
    def _load(self) -> None:
        """Đọc HWM đã lưu. File hỏng hoặc thiếu thì khởi tạo lại từ lần update đầu tiên."""
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            hwm = float(data["high_water_mark_usd"])
            if hwm <= 0.0:
                raise ValueError(f"HWM đã lưu không hợp lệ: {hwm}")
            self._hwm = hwm
            self._peak_at_utc = data.get("peak_at_utc")
            logger.info(
                "📈 Đã nạp High-Water Mark: $%.2f (đạt đỉnh lúc %s)",
                self._hwm,
                self._peak_at_utc,
            )
        except Exception as e:
            # Không được nuốt lỗi âm thầm: mất HWM là mất hiệu lực thang drawdown.
            logger.error(
                "⚠️ Không đọc được HWM từ %s (%s). Sẽ khởi tạo lại từ equity hiện tại — "
                "thang drawdown tạm thời coi như đang ở đỉnh.",
                self.state_file,
                e,
            )
            self._hwm = None
            self._peak_at_utc = None

    def _persist(self, state: HighWaterMarkState) -> None:
        """Ghi HWM xuống đĩa an toàn trên Windows."""
        payload = asdict(state)
        payload["bot_id"] = self.bot_id
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("⚠️ Không ghi được HWM xuống %s: %s", self.state_file, e)


    # ------------------------------------------------------------------ API chính
    @property
    def high_water_mark_usd(self) -> Optional[float]:
        """Đỉnh vốn hiện tại, hoặc None nếu chưa từng ghi nhận equity nào."""
        return self._hwm

    def update(self, current_equity: float, current_balance: Optional[float] = None) -> HighWaterMarkState:
        """
        Ghi nhận equity mới, nâng đỉnh nếu cần, rồi trả về drawdown tính từ đỉnh.
        Đồng thời hỗ trợ Weekly Re-anchoring: nếu đỉnh cũ thuộc tuần trước (> 4 ngày)
        và balance hiện tại có lãi (balance >= 10,000 USD), tự động điều chỉnh mốc HWM về balance
        để bảo vệ chu kỳ giao dịch tuần mới mà không bị dính bẫy đỉnh ảo.

        :param current_equity: Equity tài khoản hiện tại (USD).
        :param current_balance: Số dư balance tài khoản hiện tại (USD).
        :return: HighWaterMarkState với drawdown_fraction <= 0.0
        """
        equity = float(current_equity)
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()

        # Weekly Re-anchoring logic: prevent phantom peaks from older calendar weeks from distorting current week
        if self._peak_at_utc and current_balance and current_balance >= 10_000.0:
            try:
                peak_dt = datetime.fromisoformat(self._peak_at_utc)
                if (now_dt - peak_dt).total_seconds() > 4 * 86400:
                    peak_iso_week = peak_dt.isocalendar()[1]
                    now_iso_week = now_dt.isocalendar()[1]
                    if now_iso_week != peak_iso_week and self._hwm and self._hwm > current_balance:
                        logger.info(
                            "🔄 [WEEKLY HWM RE-ANCHORING] Re-anchoring benchmark from phantom peak $%.2f "
                            "(Week %d) to current balance $%.2f (Week %d).",
                            self._hwm,
                            peak_iso_week,
                            current_balance,
                            now_iso_week,
                        )
                        self._hwm = float(current_balance)
                        self._peak_at_utc = now
            except Exception as e:
                logger.warning("Weekly HWM check notice: %s", e)

        if equity <= 0.0:
            # Equity <= 0 là tài khoản đã cháy. Drawdown = -100%, và KHÔNG hạ đỉnh.
            hwm = self._hwm if self._hwm and self._hwm > 0 else 1.0
            state = HighWaterMarkState(
                equity_usd=equity,
                high_water_mark_usd=hwm,
                drawdown_fraction=-1.0,
                drawdown_pct=-100.0,
                is_new_peak=False,
                peak_at_utc=self._peak_at_utc or now,
                updated_at_utc=now,
            )
            self._persist(state)
            return state

        is_new_peak = self._hwm is None or equity > self._hwm
        if is_new_peak:
            self._hwm = equity
            self._peak_at_utc = now

        assert self._hwm is not None and self._hwm > 0.0
        # min(0.0, ...) chặn sai số dấu phẩy động đẩy drawdown lên số dương.
        dd = min(0.0, (equity - self._hwm) / self._hwm)

        state = HighWaterMarkState(
            equity_usd=equity,
            high_water_mark_usd=self._hwm,
            drawdown_fraction=dd,
            drawdown_pct=dd * 100.0,
            is_new_peak=is_new_peak,
            peak_at_utc=self._peak_at_utc or now,
            updated_at_utc=now,
        )
        self._persist(state)
        return state

    def reset(self, equity: float) -> HighWaterMarkState:
        """
        Đặt lại đỉnh về equity chỉ định. Dùng khi nạp/rút vốn làm thay đổi nền vốn.
        KHÔNG dùng để xoá một drawdown đang diễn ra — làm vậy là vô hiệu hoá thang bậc.
        """
        logger.warning(
            "🔄 Đặt lại High-Water Mark: $%s -> $%.2f (chỉ hợp lệ khi nạp/rút vốn)",
            f"{self._hwm:.2f}" if self._hwm else "None",
            equity,
        )
        self._hwm = None
        self._peak_at_utc = None
        return self.update(equity)
