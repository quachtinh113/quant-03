"""L1 Dữ liệu: adapter dữ liệu thị trường (MT5 -> MarketView) và các bộ lọc phiên thuần.

L4 Rủi ro không import MT5; nó nhận `MarketView` do hàm `market_view(runtime)` ở đây dựng.
Việc kéo giá/nến từ MT5 hiện vẫn nằm trong MT5ConnectionManager (l5_execution) vì lớp đó trộn
dữ liệu và gửi lệnh trong cùng một class; tách riêng là việc của một lát sau (cần golden test).
"""
from datetime import datetime, timezone
from typing import Iterable, Optional

from us_federation_quant.contracts import MarketView


def market_view(rt) -> MarketView:
    """Adapter MT5 -> MarketView (dữ liệu thị trường được tiêm vào L4; L4 không import MT5)."""
    def _mt5():
        import MetaTrader5 as mt5
        return mt5

    mgr = rt.mt5_mgr

    def reopen_state():
        if not hasattr(rt, "_symbol_reopen_first_seen_ts") or rt._symbol_reopen_first_seen_ts is None:
            rt._symbol_reopen_first_seen_ts = rt._load_sweeper_reopen_state()
        return rt._symbol_reopen_first_seen_ts

    return MarketView(
        symbol_info=lambda s: _mt5().symbol_info(s),
        symbol_tick=lambda s: _mt5().symbol_info_tick(s),
        resolve_symbol=lambda s: mgr.resolve_symbol(s) if hasattr(mgr, "resolve_symbol") else s,
        symbol_spec=lambda s: mgr.get_symbol_spec(s),
        is_market_open=lambda s: mgr.is_market_open(s),
        trade_mode_full=lambda: getattr(_mt5(), "SYMBOL_TRADE_MODE_FULL", 4),
        reopen_state=reopen_state,
    )


def is_toxic_hour(hour_utc: Optional[int], toxic_hours: Iterable[int]) -> bool:
    """Ma trận chặn khung giờ tử thần (chuyển giao phiên / thanh khoản suy giảm)."""
    if hour_utc is None:
        hour_utc = datetime.now(timezone.utc).hour
    return hour_utc in toxic_hours


def is_hk50_session_open(dt_utc: Optional[datetime] = None) -> bool:
    """Phiên HK50 (Exness/HKEX): 01:15-04:00, 05:00-08:30, 09:15-19:00 UTC; nghỉ cuối tuần."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    if dt_utc.weekday() in (5, 6):
        return False
    h, m = dt_utc.hour, dt_utc.minute
    t_min = h * 60 + m
    if 75 <= t_min < 240:
        return True
    if 300 <= t_min < 510:
        return True
    if 555 <= t_min < 1140:
        return True
    return False
