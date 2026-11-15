"""L1 Dữ liệu: adapter dữ liệu thị trường (MT5 -> MarketView) và các bộ lọc phiên thuần.

L4 Rủi ro không import MT5; nó nhận `MarketView` do hàm `market_view(runtime)` ở đây dựng.
Việc kéo giá/nến từ MT5 hiện vẫn nằm trong MT5ConnectionManager (l5_execution) vì lớp đó trộn
dữ liệu và gửi lệnh trong cùng một class; tách riêng là việc của một lát sau (cần golden test).
"""
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence, Tuple

from us_federation_quant.Document.contracts import DealView, MarketView, SymbolSpec


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


# ----------------------------------------------------------------------------------------------------
# Cổng đọc dữ liệu chuẩn hóa (MarketDataGateway). `mt5` luôn được import LƯỜI tại lúc gọi để các
# patch("MetaTrader5.…") trong test và hành vi ImportError giữ nguyên. Hàm cấp module (không phụ thuộc phương thức
# phụ trợ của runtime) để chạy được với runtime dạng MagicMock(spec=...).
# ----------------------------------------------------------------------------------------------------

def symbol_spec(rt, symbol: str, *, suffix_fallback: bool = False, mgr_fallback: bool = False) -> SymbolSpec:
    """Đọc spec mã: symbol_info(symbol) -> (resolve qua mgr nếu có) -> [thử hậu tố 'm' / bỏ 'm'] -> [spec dict của mgr].

    Thứ tự các lần gọi giữ đúng như enforce_hard_risk_cap / calculate_risk_adjusted_lot cũ (golden:
    tests/test_golden_symbol_spec_sizing.py). `mgr_fallback` chỉ đọc mgr.get_symbol_spec khi không có `info`.
    """
    import MetaTrader5 as mt5
    info = mt5.symbol_info(symbol)
    if info is None and hasattr(rt, "mt5_mgr"):
        resolved = rt.mt5_mgr.resolve_symbol(symbol)
        info = mt5.symbol_info(resolved)
    if suffix_fallback:
        if info is None and not symbol.endswith("m"):
            info = mt5.symbol_info(symbol + "m")
        if info is None and symbol.endswith("m"):
            info = mt5.symbol_info(symbol[:-1])
    spec = None
    if mgr_fallback and info is None:
        spec = rt.mt5_mgr.get_symbol_spec(symbol) if hasattr(rt, "mt5_mgr") else {}
    return SymbolSpec(symbol=symbol, info=info, spec=spec)


def bars_with_fallback(rt, attempts: Sequence[Tuple[str, str]], *, retry_below: int, mgr_timeframe: str,
                       mgr_below: int, count: int = 200) -> Any:
    """Đọc nến theo chuỗi dự phòng; trả về nến THÔ (ndarray hoặc DataFrame) hoặc None nếu vẫn thiếu.

    attempts: [(symbol, tên_khung)] gọi mt5.copy_rates_from_pos(symbol, TIMEFRAME_<khung>, 0, count); lần kế tiếp
    chỉ chạy khi kết quả trước là None hoặc ngắn hơn `retry_below`. Nếu sau đó vẫn None/ngắn hơn `mgr_below`, thử
    mgr.get_rates(attempts[0].symbol, mgr_timeframe, count=count) và chỉ nhận khi đủ `mgr_below` nến.
    Giữ đúng thứ tự gọi của hai bộ lọc EURGBP/JPY cũ (golden: tests/test_golden_trend_filters.py).
    """
    import MetaTrader5 as mt5
    rates = None
    for i, (sym, tf) in enumerate(attempts):
        if i == 0 or rates is None or len(rates) < retry_below:
            rates = mt5.copy_rates_from_pos(sym, getattr(mt5, "TIMEFRAME_" + tf), 0, count)
    if rates is None or len(rates) < mgr_below:
        df = rt.mt5_mgr.get_rates(attempts[0][0], mgr_timeframe, count=count)
        if df is not None and len(df) >= mgr_below:
            rates = df
        else:
            return None
    return rates


def _deal_view(d) -> DealView:
    return DealView(
        ticket=getattr(d, "ticket", 0), position_id=getattr(d, "position_id", 0), time=getattr(d, "time", 0),
        type=getattr(d, "type", None), entry=getattr(d, "entry", None), symbol=getattr(d, "symbol", ""),
        profit=getattr(d, "profit", 0.0), commission=getattr(d, "commission", 0.0), swap=getattr(d, "swap", 0.0),
        comment=getattr(d, "comment", ""))


def history_deals(from_ts: float, to_ts: float):
    """Lịch sử deal trong [from_ts, to_ts] (giây epoch, UTC). Trả về tuple[DealView] hoặc None (MT5 trả None).

    Giữ phân biệt None (không có dữ liệu -> caller dùng trạng thái bộ nhớ) và tuple rỗng (có dữ liệu, không deal).
    Ngoại lệ của MT5 lan ra cho caller xử lý như bản cũ. golden: tests/test_golden_deals_gate.py.
    """
    import MetaTrader5 as mt5
    from_t = datetime.fromtimestamp(from_ts, tz=timezone.utc)
    to_t = datetime.fromtimestamp(to_ts, tz=timezone.utc)
    raw = mt5.history_deals_get(from_t, to_t)
    if raw is None:
        return None
    return tuple(_deal_view(d) for d in raw)
