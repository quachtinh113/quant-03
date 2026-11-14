"""Hợp đồng dữ liệu dùng chung giữa các tầng (nguồn duy nhất, bất biến).

L4 Rủi ro KHÔNG gọi MT5: nó nhận dữ liệu đã chụp (vị thế, MarketView) và trả về một cây CHỈ THỊ
(Directive). L5 Thực thi duyệt cây đó, gọi MT5 và áp các nhánh `on_success` / `on_failure`.
Nhánh điều kiện là bắt buộc để giữ nguyên hành vi cũ (ví dụ: đóng partial thành công thì bỏ qua
khóa lãi, thất bại thì rơi xuống khóa lãi; reconcile dừng ở lệnh đóng thành công đầu tiên).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Tuple


class RiskCheck(str, Enum):
    """Tên các kiểm tra mà cổng duy nhất evaluate_risk(...) chấp nhận."""
    HARD_CAP_XAUUSD = "hard_cap_xauusd"
    HARD_CAP_INDEX = "hard_cap_index"
    HARD_CAP_GBPCHF_UK100 = "hard_cap_gbpchf_uk100"
    HARD_CAP_FOREX_PORTFOLIO = "hard_cap_forex_portfolio"
    BREAKEVEN_LOCK = "breakeven_lock"
    PROFIT_LADDER = "profit_ladder"
    TWO_TIER_EXIT = "two_tier_exit"
    RECONCILE_INDEX = "reconcile_index"
    FRIDAY_EOD_FLAT = "friday_eod_flat"
    WEEKEND_SWEEPER = "weekend_sweeper"
    LIQUIDATION_READINESS = "liquidation_readiness"


@dataclass(frozen=True)
class LogLine:
    level: str      # debug | info | warning | error | critical
    message: str    # "{error}" được thay bằng res["error"] khi dùng trong fail_log


@dataclass(frozen=True, kw_only=True)
class Directive:
    """Cơ sở chung: log trước, nhánh theo kết quả, và nhóm gom kết quả thành công."""
    pre_log: Optional[LogLine] = None
    ok_log: Optional[LogLine] = None
    fail_log: Optional[LogLine] = None
    on_success: Tuple["Directive", ...] = ()
    on_failure: Tuple["Directive", ...] = ()
    collect: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class LogDirective(Directive):
    """Chỉ ghi log (dùng pre_log)."""


@dataclass(frozen=True, kw_only=True)
class CloseDirective(Directive):
    ticket: Any
    comment: Optional[str] = None
    volume: Optional[float] = None
    positional: bool = False        # True: close_position(ticket) như bản cũ ở reconcile


@dataclass(frozen=True, kw_only=True)
class ModifyDirective(Directive):
    ticket: Any
    sl: float
    tp: Optional[float] = None
    send_tp: bool = True            # False: modify_position_sltp(ticket=, sl=) như bản cũ


@dataclass(frozen=True, kw_only=True)
class AlertDirective(Directive):
    subject: str
    body: str


@dataclass(frozen=True, kw_only=True)
class LockDirective(Directive):
    store: str                      # "ladder" | "tier2"
    ticket: Any


@dataclass(frozen=True, kw_only=True)
class TwoTierStateDirective(Directive):
    op: str                         # "set" | "delete" | "save"
    key: Optional[str] = None
    value: Optional[Mapping[str, Any]] = None
    stamp_time: bool = False        # thêm "time": now(UTC).isoformat() lúc thực thi


@dataclass(frozen=True, kw_only=True)
class ReopenPersistDirective(Directive):
    snapshot: Mapping[str, float]   # ảnh chụp dict mốc mở cửa tại thời điểm cần lưu


@dataclass(frozen=True, kw_only=True)
class RaiseDirective(Directive):
    """Tái hiện ngoại lệ của bản cũ ĐÚNG lúc nó xảy ra (sau các chỉ thị trước đó)."""
    error: BaseException


@dataclass(frozen=True)
class MarketView:
    """Dữ liệu thị trường được TIÊM vào L4 (adapter MT5 do runner/L1 dựng); L4 không import MT5."""
    symbol_info: Callable[[str], Any]
    symbol_tick: Callable[[str], Any]
    resolve_symbol: Callable[[str], Any]
    symbol_spec: Callable[[str], Any]
    is_market_open: Callable[[str], bool]
    trade_mode_full: Callable[[], int]
    reopen_state: Callable[[], dict]  # dict mốc mở cửa theo mã (nạp lười như bản cũ)


@dataclass(frozen=True)
class RiskEvaluationResult:
    directives: Tuple[Directive, ...] = ()
    delegate: Optional[str] = None   # "friday_eod_flat": sweeper giao lại cho enforce_friday_eod_flat
    ready: Optional[bool] = None     # chỉ dùng cho LIQUIDATION_READINESS
    reason: Optional[str] = None
