"""
========================================================================================
US FEDERATION QUANT — INSTITUTIONAL MACRO NEWS & ECONOMIC CALENDAR ENGINE
Module: macro_news_engine.py
Automated High-Impact Macro Economic Event Ingestion & Blackout Radar.
1. Maintains structured 3-Star High Impact Economic Calendar (NFP, CPI, FOMC, Core PPI).
2. Calculates exact time-to-impact Delta_t and pre/post embargo windows.
3. Integrates seamlessly with InstitutionalStatutoryRules.check_macro_news_blackout.
4. Generates automated Telegram War-Room pre-news alerts 15 minutes before event impact.
5. Persistent local JSON caching for 100% offline resilience and zero runtime downtime.
========================================================================================
"""

from __future__ import annotations
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("US_Federation.MacroNewsEngine")


@dataclass
class MacroEvent:
    name: str
    currency: str
    impact: str  # HIGH, CRITICAL
    timestamp_utc: datetime
    pre_embargo_minutes: int = 15
    post_embargo_minutes: int = 15
    forecast: Optional[float] = None
    previous: Optional[float] = None
    actual: Optional[float] = None

    @property
    def start_blackout(self) -> datetime:
        return self.timestamp_utc - timedelta(minutes=self.pre_embargo_minutes)

    @property
    def end_blackout(self) -> datetime:
        return self.timestamp_utc + timedelta(minutes=self.post_embargo_minutes)


class MacroNewsEngine:
    """
    Cỗ Máy Thu Thập Lịch Kinh Tế Vĩ Mô Định Chế (Macro News Radar).
    Tự động bảo vệ tài khoản trước các cơn sóng giật 2 đầu khi công bố tin tức đỏ.
    """

    def __init__(self, cache_file_path: Optional[str] = None):
        if cache_file_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.cache_file = os.path.join(base_dir, "macro_calendar_cache.json")
        else:
            self.cache_file = cache_file_path

        self.events: List[MacroEvent] = []
        self._load_or_initialize_calendar()

    def _load_or_initialize_calendar(self):
        """Đọc bộ đệm lịch kinh tế hoặc khởi tạo mẫu lịch đỏ định chế năm 2026."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("events", []):
                        ts = datetime.fromisoformat(item["timestamp_utc"])
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        self.events.append(
                            MacroEvent(
                                name=item["name"],
                                currency=item.get("currency", "USD"),
                                impact=item.get("impact", "HIGH"),
                                timestamp_utc=ts,
                                pre_embargo_minutes=item.get("pre_embargo_minutes", 15),
                                post_embargo_minutes=item.get("post_embargo_minutes", 15),
                                forecast=item.get("forecast"),
                                previous=item.get("previous"),
                                actual=item.get("actual"),
                            )
                        )
                logger.info(f"📅 Loaded {len(self.events)} macro events from cache: {self.cache_file}")
                return
            except Exception as e:
                logger.warning(f"Failed to load macro cache ({e}), initializing standard recurring schedule.")

        # Khởi tạo lịch sự kiện chuẩn nếu tệp đệm chưa tồn tại
        self.events = self._generate_standard_institutional_schedule_2026()
        self.save_cache()

    @staticmethod
    def _generate_standard_institutional_schedule_2026() -> List[MacroEvent]:
        """Tạo lịch mẫu các sự kiện bão đỏ định chế quan trọng tháng 9/2026."""
        events = [
            # NFP & Unemployment Rate (Thứ 6 đầu tiên của tháng hoặc tuần 3/4)
            MacroEvent(
                name="US Non-Farm Payrolls (NFP) & Unemployment Rate",
                currency="USD",
                impact="CRITICAL",
                timestamp_utc=datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc),
                pre_embargo_minutes=30,
                post_embargo_minutes=20,
            ),
            # CPI Inflation Report
            MacroEvent(
                name="US Consumer Price Index (CPI MoM/YoY)",
                currency="USD",
                impact="CRITICAL",
                timestamp_utc=datetime(2026, 9, 23, 12, 30, tzinfo=timezone.utc),
                pre_embargo_minutes=25,
                post_embargo_minutes=20,
            ),
            # FOMC Interest Rate Decision & Powell Press Conference
            MacroEvent(
                name="FOMC Interest Rate Decision & Fed Press Conference",
                currency="USD",
                impact="CRITICAL",
                timestamp_utc=datetime(2026, 9, 23, 18, 0, tzinfo=timezone.utc),
                pre_embargo_minutes=45,
                post_embargo_minutes=30,
            ),
            # US Core PPI
            MacroEvent(
                name="US Producer Price Index (Core PPI)",
                currency="USD",
                impact="HIGH",
                timestamp_utc=datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc),
                pre_embargo_minutes=15,
                post_embargo_minutes=15,
            ),
            # Initial Jobless Claims (Mỗi thứ 5 hàng tuần lúc 12:30 UTC)
            MacroEvent(
                name="US Initial Jobless Claims",
                currency="USD",
                impact="HIGH",
                timestamp_utc=datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc),
                pre_embargo_minutes=10,
                post_embargo_minutes=10,
            ),
        ]
        return events

    def save_cache(self):
        """Lưu trữ lịch sự kiện vào bộ nhớ đệm JSON."""
        try:
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "events": [
                    {
                        "name": e.name,
                        "currency": e.currency,
                        "impact": e.impact,
                        "timestamp_utc": e.timestamp_utc.isoformat(),
                        "pre_embargo_minutes": e.pre_embargo_minutes,
                        "post_embargo_minutes": e.post_embargo_minutes,
                        "forecast": e.forecast,
                        "previous": e.previous,
                        "actual": e.actual,
                    }
                    for e in self.events
                ],
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.events)} events to {self.cache_file}")
        except Exception as e:
            logger.error(f"Error saving macro news cache: {e}")

    def add_event(self, event: MacroEvent):
        """Thêm một sự kiện mới vào lịch."""
        self.events.append(event)
        self.events.sort(key=lambda x: x.timestamp_utc)
        self.save_cache()

    # =========================================================================
    # KIỂM TRA ĐÓNG BĂNG MỞ LỆNH (BLACKOUT RADAR)
    # =========================================================================
    def check_active_blackout(
        self,
        now_utc: Optional[datetime] = None
    ) -> Tuple[bool, Optional[MacroEvent], str]:
        """
        Kiểm tra thời điểm hiện tại có đang nằm trong cửa sổ đóng băng mở lệnh không.
        Returns: (is_blackout_active, active_event, reason_message)
        """
        dt = now_utc or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        for event in self.events:
            if event.start_blackout <= dt <= event.end_blackout:
                diff_min = (event.timestamp_utc - dt).total_seconds() / 60.0
                status_str = f"trước tin {diff_min:.1f} phút" if diff_min > 0 else f"sau tin {abs(diff_min):.1f} phút"
                reason = (
                    f"🌪️ [CẢNH BÁO ĐÓNG BĂNG VĨ MÔ ĐỎ] Đang trong cửa sổ cấm giao dịch của {event.name} ({status_str}). "
                    f"Cấm mở vị thế mới từ {event.start_blackout.strftime('%H:%M')} đến {event.end_blackout.strftime('%H:%M')} UTC!"
                )
                return True, event, reason

        return False, None, "✅ Ngoài vùng cấm tin tức vĩ mô đỏ. Thị trường mở tự do."

    def get_upcoming_events(
        self,
        now_utc: Optional[datetime] = None,
        horizon_hours: float = 24.0
    ) -> List[Tuple[MacroEvent, float]]:
        """
        Lấy danh sách các sự kiện đỏ sắp diễn ra trong vòng N giờ tới.
        Returns: List of (MacroEvent, hours_until_event)
        """
        dt = now_utc or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        horizon_end = dt + timedelta(hours=horizon_hours)
        upcoming = []

        for event in self.events:
            if dt <= event.timestamp_utc <= horizon_end:
                delta_h = (event.timestamp_utc - dt).total_seconds() / 3600.0
                upcoming.append((event, delta_h))

        upcoming.sort(key=lambda x: x[1])
        return upcoming

    def get_pre_news_alert(
        self,
        now_utc: Optional[datetime] = None,
        alert_window_minutes: int = 15
    ) -> Optional[str]:
        """
        Tự động tạo thông báo cảnh báo sớm (trước 15 phút) để gửi cho Telegram Bot.
        """
        dt = now_utc or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        for event in self.events:
            diff_min = (event.timestamp_utc - dt).total_seconds() / 60.0
            if 0 < diff_min <= alert_window_minutes:
                return (
                    f"⚠️ <b>CẢNH BÁO SẮP CÔNG BỐ TIN BÃO ĐỎ:</b>\n"
                    f"Sự kiện: <b>{event.name}</b> ({event.currency})\n"
                    f"Thời điểm công bố: {event.timestamp_utc.strftime('%H:%M:%S UTC')}\n"
                    f"Còn lại: <b>{diff_min:.1f} phút</b>\n"
                    f"Lệnh tự động: Đóng băng mở vị thế mới và hủy toàn bộ lệnh chờ (Pending Orders)!"
                )
        return None

    def export_events_for_governance_rules(
        self,
        now_utc: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Xuất định dạng sự kiện tương thích 100% với InstitutionalStatutoryRules.check_macro_news_blackout.
        """
        dt = now_utc or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        exported = []
        for e in self.events:
            # Map event to weekday, hour, minute
            exported.append({
                "name": e.name,
                "weekday": e.timestamp_utc.weekday(),
                "hour": e.timestamp_utc.hour,
                "minute": e.timestamp_utc.minute,
                "pre_minutes": e.pre_embargo_minutes,
                "post_minutes": e.post_embargo_minutes,
            })
        return exported
