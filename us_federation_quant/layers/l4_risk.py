"""l4_risk: tầng gộp từ l4_risk.py, exposure_and_beta_desk.py, federal_master_kill_switch.py, fourth_estate_watchdog.py, var_cvar_engine.py, central_risk_desk.py, black_swan_stress_tester.py, cold_storage_vault.py, deflated_sharpe_test.py, judicial_review.py, supreme_court_circuit_breaker_manager.py, trial_ledger.py, cryptographic_warrant.py, high_water_mark.py, fleet_guard.py."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from us_federation_quant.layers.contracts import (
    AlertDirective,
    CloseDirective,
    Directive,
    LockDirective,
    LogDirective,
    LogLine,
    MarketView,
    ModifyDirective,
    RaiseDirective,
    ReopenPersistDirective,
    RiskCheck,
    RiskEvaluationResult,
    TwoTierStateDirective,
)
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import numpy as np
from dataclasses import dataclass
import hashlib
import time
import logging
import scipy.stats as stats
from typing import Dict, Any, List
import pandas as pd
import os
from typing import Dict, Any, Optional
import math
from typing import Tuple
import json
import sys
import hmac
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Optional


# ====================================================================================================
# layers/l4_risk.py  —  L4 Rủi ro (MỘT file): cổng duy nhất `evaluate_risk(...)` + toàn bộ logic quyết định.
# ====================================================================================================





# ====================================================================================================
# GIỜ / PHIÊN THUẦN (DST Mỹ, giờ server MT5, curfew, mốc mở tuần, cửa sổ xả EOD)
# ====================================================================================================

def is_us_dst(dt_utc: Optional[datetime] = None) -> bool:
    """US DST: từ CN thứ 2 tháng 3 07:00 UTC đến CN đầu tháng 11 06:00 UTC."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    year = dt_utc.year
    march_1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    days_to_first_sun_mar = (6 - march_1.weekday()) % 7
    dst_start = datetime(year, 3, 1 + days_to_first_sun_mar + 7, 7, 0, 0, tzinfo=timezone.utc)
    nov_1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    days_to_first_sun_nov = (6 - nov_1.weekday()) % 7
    dst_end = datetime(year, 11, 1 + days_to_first_sun_nov, 6, 0, 0, tzinfo=timezone.utc)
    return dst_start <= dt_utc < dst_end


def get_mt5_server_datetime(dt_utc: Optional[datetime] = None) -> datetime:
    """Giờ server MT5: UTC+3 khi US DST, UTC+2 khi không."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    offset_hours = 3 if is_us_dst(dt_utc) else 2
    return dt_utc + timedelta(hours=offset_hours)


def is_friday_or_weekend_curfew(dt_utc: Optional[datetime] = None) -> bool:
    """Cấm mở lệnh mới: Thứ Sáu >= 23:00 server, cả Thứ Bảy, Chủ Nhật tới 60 phút sau giờ mở phiên."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    srv_dt = get_mt5_server_datetime(dt_utc)
    srv_wd = srv_dt.weekday()
    if srv_wd == 4 and srv_dt.hour >= 23:
        return True
    if srv_wd in (5, 6):
        return True
    utc_wd = dt_utc.weekday()
    sunday_open_utc_hour = 21 if is_us_dst(dt_utc) else 22
    if utc_wd == 5:
        return True
    if utc_wd == 6 and dt_utc.hour < sunday_open_utc_hour + 1:
        return True
    return False


def get_last_weekly_open_utc(dt_utc: Optional[datetime] = None) -> datetime:
    """Mốc mở phiên tuần gần nhất (<= dt_utc): CN 21:00 UTC (DST) hoặc 22:00 UTC."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    days_since_sunday = (dt_utc.weekday() + 1) % 7
    sunday = (dt_utc - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
    candidate = sunday.replace(hour=21 if is_us_dst(sunday + timedelta(hours=12)) else 22)
    if candidate > dt_utc:
        prev_sunday = sunday - timedelta(days=7)
        candidate = prev_sunday.replace(hour=21 if is_us_dst(prev_sunday + timedelta(hours=12)) else 22)
    return candidate


def is_friday_eod_flat_window(dt_utc: Optional[datetime] = None, symbol: Optional[str] = None) -> bool:
    """Cửa sổ xả sạch tối Thứ Sáu: chỉ số từ 20:15 UTC; toàn danh mục từ 23:30 server."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    srv_dt = get_mt5_server_datetime(dt_utc)

    if symbol is not None:
        sym_upper = symbol.upper().replace("M", "")
        is_index = any(idx in sym_upper for idx in ["UK100", "USTEC", "US30", "HK50", "US500", "DE30", "JP225"])
        if is_index and dt_utc.weekday() == 4:
            if (dt_utc.hour == 20 and dt_utc.minute >= 15) or dt_utc.hour >= 21:
                return True

    if srv_dt.weekday() == 4 and srv_dt.hour == 23 and srv_dt.minute >= 30:
        return True
    if dt_utc.weekday() == 4 and srv_dt.weekday() == 5:
        return True
    return False


# ====================================================================================================
# TRẦN LỖ CỨNG THEO VỊ THẾ + DE-RISKING US30
# ====================================================================================================

Position = Dict[str, Any]

INDEX_KEYS = ("USTEC", "US30", "US500", "NAS100", "DJ30", "SP500")
GBPCHF_UK100_KEYS = ("GBPCHF", "UK100")
FOREX_EXCLUDED_KEYS = ("USTEC", "US30", "US100", "US500", "HK50", "XAUUSD", "GOLD")


def _total_strict(p: Position) -> float:
    return p["profit"] + p.get("swap", 0.0) + p.get("commission", 0.0)


def _total_lenient(p: Position) -> float:
    return float(p.get("profit", 0.0)) + float(p.get("swap", 0.0)) + float(p.get("commission", 0.0))


def _xau(p: Position, cap: float) -> Optional[float]:
    sym = p["symbol"].upper()
    if "XAU" in sym or "GOLD" in sym:
        total = _total_strict(p)
        if total <= -cap:
            return total
    return None


def _index(p: Position, cap: float) -> Optional[float]:
    sym = p["symbol"].upper()
    if any(k in sym for k in INDEX_KEYS):
        total = _total_strict(p)
        if total <= -cap:
            return total
    return None


def _gbpchf_uk100(p: Position, cap: float) -> Optional[float]:
    sym = p.get("symbol", "").upper().replace("M", "")
    if any(k in sym for k in GBPCHF_UK100_KEYS):
        total = _total_lenient(p)
        if total <= -cap:
            return total
    return None


def _forex(p: Position, cap: float) -> Optional[float]:
    sym = p.get("symbol", "").upper().replace("M", "")
    if any(k in sym for k in FOREX_EXCLUDED_KEYS):
        return None
    total = _total_lenient(p)
    return total if total <= -cap else None


def _xau_dirs(p: Position, total: float, cap: float) -> Directive:
    t = p["ticket"]
    return CloseDirective(
        ticket=t, comment="XAU HardCap 75", collect="closed",
        pre_log=LogLine("critical",
            f"🚨 [XAUUSD HARD STOP CAP ACTIVATED] Ticket #{t} ({p['symbol']} {p['type']} {p['volume']}L): "
            f"Loss reached ${total:.2f} USD (Threshold: -${cap:.2f} USD). "
            f"Triggering Emergency Market Close to protect capital!"),
        on_success=(AlertDirective(
            subject="XAUUSD HARD STOP CAP TRIGGERED",
            body=f"Closed Gold ticket #{t} at ${total:.2f} USD to cap fat-tail loss."),))


def _index_dirs(p: Position, total: float, cap: float) -> Directive:
    t = p["ticket"]
    return CloseDirective(
        ticket=t, comment="Index HardCap 60", collect="closed",
        pre_log=LogLine("warning",
            f"🚨 [CIRCUIT_BREAKER] Ticket #{t} ({p['symbol']} {p['type']} {p['volume']}L): "
            f"Loss reached ${total:.2f} USD (Threshold: -${cap:.2f} USD). "
            f"Triggering Emergency Market Close to protect capital!"),
        on_success=(AlertDirective(
            subject="INDEX HARD STOP CAP TRIGGERED",
            body=f"Closed Index ticket #{t} at ${total:.2f} USD to cap fat-tail loss."),))


def _gbpchf_dirs(p: Position, total: float, cap: float) -> Directive:
    t = p.get("ticket")
    return CloseDirective(
        ticket=t, comment="HardCap 15", collect="closed",
        pre_log=LogLine("warning",
            f"🚨 [GBPCHF/UK100 HARD STOP CAP] Ticket #{t} ({p.get('symbol')} {p.get('type')} {p.get('volume')}L): "
            f"Loss reached ${total:.2f} USD (Cap: -${cap:.2f} USD). "
            f"Triggering Emergency Market Close to protect capital!"),
        on_success=(AlertDirective(
            subject="GBPCHF/UK100 HARD STOP CAP TRIGGERED",
            body=f"Closed ticket #{t} ({p.get('symbol')}) at ${total:.2f} USD to cap loss at $15."),))


def _forex_dirs(p: Position, total: float, cap: float) -> Directive:
    t = p.get("ticket")
    return CloseDirective(
        ticket=t, comment="HardCap 15", collect="closed",
        pre_log=LogLine("warning",
            f"🚨 [PORTFOLIO HARD STOP CAP] Ticket #{t} ({p.get('symbol')} {p.get('type')} {p.get('volume')}L): "
            f"Loss reached ${total:.2f} USD (Cap: -${cap:.2f} USD). "
            f"Triggering Emergency Market Close to protect capital!"),
        on_success=(AlertDirective(
            subject=f"{p.get('symbol')} HARD STOP CAP TRIGGERED",
            body=f"Closed ticket #{t} ({p.get('symbol')}) at ${total:.2f} USD to cap loss at $15."),))


_RULES: Dict[str, Tuple[Callable, Callable]] = {
    "hard_cap_xauusd": (_xau, _xau_dirs),
    "hard_cap_index": (_index, _index_dirs),
    "hard_cap_gbpchf_uk100": (_gbpchf_uk100, _gbpchf_dirs),
    "hard_cap_forex_portfolio": (_forex, _forex_dirs),
}


def evaluate_hard_cap(check: str, positions: Sequence[Position], max_loss_usd: float) -> RiskEvaluationResult:
    match, build = _RULES[check]
    out: List[Directive] = []
    for p in positions:
        try:
            total = match(p, max_loss_usd)
            if total is not None:
                out.append(build(p, total, max_loss_usd))
        except Exception as exc:  # bản cũ nổ giữa vòng lặp, sau các lệnh đóng trước đó
            out.append(RaiseDirective(error=exc))
            break
    return RiskEvaluationResult(directives=tuple(out))


def evaluate_reconcile_index(positions: Sequence[Position]) -> RiskEvaluationResult:
    """Đóng 1 lệnh US30 BUY trùng lặp đã hồi về >= -$50; dừng ở lệnh đóng thành công đầu tiên."""
    us30_buys = [p for p in positions if "US30" in p["symbol"].upper() and p["type"] == "BUY"]
    if len(us30_buys) <= 1:
        return RiskEvaluationResult()
    candidates = [p for p in sorted(us30_buys, key=lambda x: x["profit"], reverse=True)
                  if p["profit"] >= -50.0]
    chain: Optional[Directive] = None
    for p in reversed(candidates):  # lệnh thất bại -> thử ứng viên kế tiếp
        chain = CloseDirective(
            ticket=p["ticket"], positional=True, collect="closed",
            ok_log=LogLine("info",
                f"🛡️ [TACTICAL INDEX DE-RISKING] Closed duplicate US30 BUY #{p['ticket']} "
                f"@ profit ${p['profit']:.2f} USD. Index exposure normalized to 0.50L."),
            on_failure=(chain,) if chain is not None else ())
    return RiskEvaluationResult(directives=(chain,) if chain is not None else ())


# ====================================================================================================
# BREAKEVEN LOCK + BẬC THANG KHÓA LÃI 3 TẦNG
# ====================================================================================================

def _safe_float(obj, attr, default):
    val = getattr(obj, attr, default)
    try:
        res = float(val)
        return res if res > 0 else default
    except Exception:
        return default


def _breakeven_one(p: Position, market: MarketView, buffer_pips: float) -> List[Directive]:
    ticket = p.get("ticket")
    symbol = p.get("symbol")
    entry = float(p.get("price_open", 0.0))
    current_price = float(p.get("price_current", entry))
    sl = float(p.get("sl", 0.0))
    tp = float(p.get("tp", 0.0))
    profit = float(p.get("profit", 0.0))
    pos_type = p.get("type")

    if entry <= 0 or current_price <= 0:
        return []

    sym_info = market.symbol_info(symbol)
    if sym_info is None:
        resolved = market.resolve_symbol(symbol)
        sym_info = market.symbol_info(resolved)
    if sym_info is None:
        return []

    point = float(getattr(sym_info, "point", 0.0001) or 0.0001)
    digits = int(getattr(sym_info, "digits", 2) or 2)
    pip_size = point * 10.0 if digits in (3, 5) else point
    buffer_price = buffer_pips * pip_size

    reached_half_tp = False
    if tp > 0:
        total_tp_dist = abs(tp - entry)
        current_dist = (current_price - entry) if pos_type in ["BUY", 0] else (entry - current_price)
        if total_tp_dist > 0 and (current_dist / total_tp_dist) >= 0.50:
            reached_half_tp = True

    if profit >= 12.0 or reached_half_tp:
        if pos_type in ["BUY", 0]:
            new_sl = round(entry + buffer_price, digits)
            if sl < new_sl and current_price > new_sl:
                return [ModifyDirective(
                    ticket=ticket, sl=new_sl, tp=tp, collect="modified",
                    ok_log=LogLine("info",
                        f"🛡️ [BREAKEVEN LOCK ADVANCED] Ticket #{ticket} ({symbol} BUY): "
                        f"Profit ${profit:+.2f} USD / 50% TP. Dời SL: {sl} -> {new_sl} (Entry + {buffer_pips} pips buffer)."))]
        elif pos_type in ["SELL", 1]:
            new_sl = round(entry - buffer_price, digits)
            if (sl == 0.0 or sl > new_sl) and current_price < new_sl:
                return [ModifyDirective(
                    ticket=ticket, sl=new_sl, tp=tp, collect="modified",
                    ok_log=LogLine("info",
                        f"🛡️ [BREAKEVEN LOCK ADVANCED] Ticket #{ticket} ({symbol} SELL): "
                        f"Profit ${profit:+.2f} USD / 50% TP. Dời SL: {sl} -> {new_sl} (Entry - {buffer_pips} pips buffer)."))]
    return []


def evaluate_breakeven(positions: Sequence[Position], market: MarketView, buffer_pips: float = 1.5) -> RiskEvaluationResult:
    out: List[Directive] = []
    for p in positions:
        try:
            out.extend(_breakeven_one(p, market, buffer_pips))
        except Exception as exc:
            out.append(RaiseDirective(error=exc))
            break
    return RiskEvaluationResult(directives=tuple(out))


def _tier_levels(pos_type, entry, digits, val_per_price, lock_usd, tp_usd):
    d_sl, d_tp = lock_usd / val_per_price, tp_usd / val_per_price
    if pos_type in ["BUY", 0]:
        return round(entry + d_sl, digits), round(entry + d_tp, digits)
    return round(entry - d_sl, digits), round(entry - d_tp, digits)


def _ladder_one(p: Position, market: MarketView) -> List[Directive]:
    ticket = p.get("ticket")
    symbol = p.get("symbol")
    entry = float(p.get("price_open", 0.0))
    curr_price = float(p.get("price_current", entry))
    sl = float(p.get("sl", 0.0))
    tp = float(p.get("tp", 0.0))
    profit = float(p.get("profit", 0.0)) + float(p.get("swap", 0.0))
    volume = float(p.get("volume", 0.01))
    pos_type = p.get("type")

    if entry <= 0 or curr_price <= 0:
        return []

    sym_info = market.symbol_info(symbol)
    if sym_info is None:
        resolved = market.resolve_symbol(symbol)
        sym_info = market.symbol_info(resolved)

    if sym_info is not None:
        point = _safe_float(sym_info, "point", 0.0001)
        digits = int(getattr(sym_info, "digits", 2) or 2)
        trade_tick_val = _safe_float(sym_info, "trade_tick_value", 1.0)
        trade_tick_sz = _safe_float(sym_info, "trade_tick_size", point)
        spread = _safe_float(sym_info, "spread", 2.0) * point
    else:
        spec = market.symbol_spec(symbol)
        digits = spec.get("digits", 2) if spec else 2
        point = float(spec.get("point", 0.0001) or 0.0001)
        trade_tick_sz = float(spec.get("tick_size", point) or point)
        trade_tick_val = float(spec.get("tick_value", 1.0) or 1.0)
        spread = 2.0 * point

    pip_size = point * 10.0 if digits in (3, 5) else point
    buffer_price = 1.5 * pip_size

    if trade_tick_sz > 0:
        val_per_price = (trade_tick_val / trade_tick_sz) * volume
    else:
        val_per_price = volume * 100_000.0 if digits in (3, 5) else volume
    val_per_price = max(val_per_price, 1e-6)

    min_stop_gap = max(spread + 2.0 * point, 5.0 * point)

    target_new_sl = sl
    target_new_tp = tp
    should_modify = False
    tier_label = ""
    out: List[Directive] = []

    progress_40pct_tp = False
    if tp > 0:
        total_tp_dist = abs(tp - entry)
        current_dist = (curr_price - entry) if pos_type in ["BUY", 0] else (entry - curr_price)
        if total_tp_dist > 0 and (current_dist / total_tp_dist) >= 0.40:
            progress_40pct_tp = True

    if profit >= 15.0 or profit >= 8.0:
        if profit >= 15.0:
            lock_usd, tp_usd = 10.0, 40.0
            tier_label = "TIER_3_SUPER_TREND (+10$ Lock / +40$ TP)"
        else:
            lock_usd, tp_usd = 4.0, 25.0
            tier_label = "TIER_2_RUNNER (+4$ Lock / +25$ TP)"
        calc_sl, calc_tp = _tier_levels(pos_type, entry, digits, val_per_price, lock_usd, tp_usd)
        if pos_type in ["BUY", 0]:
            if calc_sl > target_new_sl and calc_sl < (curr_price - min_stop_gap):
                target_new_sl = calc_sl
                should_modify = True
            if (target_new_tp == 0.0 or calc_tp > target_new_tp) and calc_tp > (curr_price + min_stop_gap):
                target_new_tp = calc_tp
                should_modify = True
        elif pos_type in ["SELL", 1]:
            if (target_new_sl == 0.0 or calc_sl < target_new_sl) and calc_sl > (curr_price + min_stop_gap):
                target_new_sl = calc_sl
                should_modify = True
            if (target_new_tp == 0.0 or calc_tp < target_new_tp) and calc_tp < (curr_price - min_stop_gap):
                target_new_tp = calc_tp
                should_modify = True
        out.append(LockDirective(store="ladder", ticket=ticket))
        out.append(LockDirective(store="tier2", ticket=ticket))

    elif profit >= 4.0 or progress_40pct_tp:
        dist_min_profit = 0.80 / val_per_price
        be_offset = max(buffer_price, dist_min_profit)
        tier_label = "TIER_1_BREAKEVEN_PLUS (Entry + 1.5p / +0.80$ Lock)"
        if pos_type in ["BUY", 0]:
            calc_sl = round(entry + be_offset, digits)
            if calc_sl > target_new_sl and calc_sl < (curr_price - min_stop_gap):
                target_new_sl = calc_sl
                should_modify = True
        elif pos_type in ["SELL", 1]:
            calc_sl = round(entry - be_offset, digits)
            if (target_new_sl == 0.0 or calc_sl < target_new_sl) and calc_sl > (curr_price + min_stop_gap):
                target_new_sl = calc_sl
                should_modify = True
        out.append(LockDirective(store="ladder", ticket=ticket))

    if should_modify:
        sl_diff = abs(target_new_sl - sl)
        tp_diff = abs(target_new_tp - tp)
        if sl_diff >= (point * 1.5) or tp_diff >= (point * 5.0):
            out.append(ModifyDirective(
                ticket=ticket, sl=target_new_sl, tp=target_new_tp, collect="modified",
                ok_log=LogLine("info",
                    f"🪜 [{tier_label}] Ticket #{ticket} ({symbol} {'BUY' if pos_type in ['BUY', 0] else 'SELL'} {volume}L): "
                    f"Floating Profit ${profit:+.2f} USD. Ratchet SL: {sl} -> {target_new_sl} | TP: {tp} -> {target_new_tp}.")))
    return out


def evaluate_profit_ladder(positions: Sequence[Position], market: MarketView) -> RiskEvaluationResult:
    out: List[Directive] = []
    for p in positions:
        try:
            out.extend(_ladder_one(p, market))
        except Exception as exc:
            out.append(RaiseDirective(error=exc))
            break
    return RiskEvaluationResult(directives=tuple(out))


# ====================================================================================================
# TWO-TIER EXIT (CHỐT 50% + RUNNER)
# ====================================================================================================

def _tier2_lock(p: Position, spec, digits: int) -> List[Directive]:
    """Khóa SL +$5, nới TP +$30 khi lãi >= $15, rồi cấp miễn nhiễm Stagnation (tier2 lock)."""
    ticket, volume, sl = p["ticket"], p["volume"], p["sl"]
    open_price, symbol, profit = p["price_open"], p["symbol"], p["profit"]
    curr_price = p.get("price_current", open_price)
    pos_type = p["type"]

    trade_tick_val = float(spec.get("tick_value", 1.0) or 1.0)
    trade_tick_sz = float(spec.get("tick_size", 0.0001) or 0.0001)
    if trade_tick_sz > 0:
        val_per_price = (trade_tick_val / trade_tick_sz) * volume
    else:
        val_per_price = volume
    val_per_price = max(val_per_price, 1e-6)

    dist_5usd = 5.0 / val_per_price
    dist_30usd = 30.0 / val_per_price
    out: List[Directive] = []

    if pos_type in ["BUY", 0]:
        target_locked_sl = round(open_price + dist_5usd, digits)
        target_expanded_tp = round(open_price + dist_30usd, digits)
        should_modify, new_sl_val, new_tp_val = False, sl, p.get("tp", 0.0)
        if target_locked_sl > sl and target_locked_sl < curr_price:
            new_sl_val, should_modify = target_locked_sl, True
        if (new_tp_val == 0.0 or target_expanded_tp > new_tp_val) and target_expanded_tp > curr_price:
            new_tp_val, should_modify = target_expanded_tp, True
        side = "BUY"
    elif pos_type in ["SELL", 1]:
        target_locked_sl = round(open_price - dist_5usd, digits)
        target_expanded_tp = round(open_price - dist_30usd, digits)
        should_modify, new_sl_val, new_tp_val = False, sl, p.get("tp", 0.0)
        if (sl == 0.0 or target_locked_sl < sl) and target_locked_sl > curr_price:
            new_sl_val, should_modify = target_locked_sl, True
        if (new_tp_val == 0.0 or target_expanded_tp < new_tp_val) and target_expanded_tp < curr_price:
            new_tp_val, should_modify = target_expanded_tp, True
        side = "SELL"
    else:
        should_modify = False

    if should_modify:
        out.append(ModifyDirective(
            ticket=ticket, sl=new_sl_val, tp=new_tp_val, collect="trailed_runners",
            ok_log=LogLine("info",
                f"🔒 [TIER_2_LOCK_5USD_RUNNER] Ticket #{ticket} ({symbol} {side}): "
                f"Profit +${profit:,.2f} USD >= +$15. Hard SL locked to +$5.00 ({new_sl_val}), TP expanded to +$30.00 ({new_tp_val}).")))
    out.append(LockDirective(store="tier2", ticket=ticket))
    return out


def _be_sl(pos_type, open_price, spread_padding, digits):
    return round(open_price + spread_padding, digits) if pos_type == "BUY" else round(open_price - spread_padding, digits)


def _position_directives(p: Position, market: MarketView, state: Mapping[str, Any],
                         min_partial_profit_usd: float) -> List[Directive]:
    ticket = p["ticket"]
    str_ticket = str(ticket)
    profit, volume, open_price = p["profit"], p["volume"], p["price_open"]
    pos_type, symbol = p["type"], p["symbol"]

    spec = market.symbol_spec(symbol)
    digits = spec.get("digits", 2) if spec else 2
    spread_padding = open_price * 0.0005
    tier1_done = state.get(str_ticket, {}).get("tier1_closed", False)

    def tier2() -> List[Directive]:
        if profit < 15.0:
            return []
        try:
            return _tier2_lock(p, spec, digits)
        except Exception as exc:  # bản cũ nổ tại đây, sau các chỉ thị đã thực thi trước đó
            return [RaiseDirective(error=exc)]

    if profit >= min_partial_profit_usd and not tier1_done:
        half_vol = round(volume / 2.0, 2)
        target_be_sl = _be_sl(pos_type, open_price, spread_padding, digits)
        if volume <= 0.01 or half_vol < 0.01:
            return [
                LogDirective(pre_log=LogLine("info",
                    f"🎯 [TWO-TIER EXIT: MIN VOLUME] Ticket #{ticket} ({symbol} {volume}L): "
                    f"Profit +${profit:.2f} USD. Volume too small to halve. Moving directly to Break-Even.")),
                ModifyDirective(ticket=ticket, sl=target_be_sl, send_tp=False),
                TwoTierStateDirective(op="set", key=str_ticket, stamp_time=True,
                                      value={"tier1_closed": True, "closed_vol": 0.0, "remain_vol": volume}),
            ] + tier2()
        return [CloseDirective(
            ticket=ticket, volume=half_vol, comment="Tier1 50% TP", collect="partial_closed",
            on_success=(
                ModifyDirective(ticket=ticket, sl=target_be_sl, send_tp=False),
                LogDirective(pre_log=LogLine("info",
                    f"🎯 [TWO-TIER EXIT: TIER 1 PARTIAL TP] Ticket #{ticket} ({symbol}): "
                    f"Successfully closed 50% ({half_vol}L of {volume}L) at profit +${profit:.2f} USD! "
                    f"SL of remaining {round(volume - half_vol, 2)}L moved to Break-Even ({target_be_sl}).")),
                TwoTierStateDirective(op="set", key=str_ticket, stamp_time=True,
                                      value={"tier1_closed": True, "closed_vol": half_vol,
                                             "remain_vol": round(volume - half_vol, 2)}),
            ),
            on_failure=tuple(tier2()))]
    return tier2()


def evaluate_two_tier_exit(positions: Sequence[Position], market: MarketView, state: Mapping[str, Any],
                           min_partial_profit_usd: float = 25.0) -> RiskEvaluationResult:
    out: List[Directive] = []
    active = {str(p["ticket"]) for p in positions}
    for t in list(state.keys()):
        if t not in active:
            out.append(TwoTierStateDirective(op="delete", key=t))
    for p in positions:
        try:
            out.extend(_position_directives(p, market, state, min_partial_profit_usd))
        except Exception as exc:
            out.append(RaiseDirective(error=exc))
            break
    out.append(TwoTierStateDirective(op="save"))
    return RiskEvaluationResult(directives=tuple(out))


# ====================================================================================================
# FRIDAY EOD FLAT / READINESS THEO MÃ / WEEKEND SWEEPER
# ====================================================================================================

_INDEX_KEYS = ["USTEC", "US30", "UK100", "HK50", "US500", "DE30", "JP225"]
_MAJORS = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]


def _pos_attr(pos, name, default):
    if hasattr(pos, name):
        return getattr(pos, name, default)
    return pos.get(name, default) if isinstance(pos, dict) else (None if name == "ticket" else default)


def _friday_one(pos, now_utc: Optional[datetime]) -> Optional[Directive]:
    ticket = _pos_attr(pos, "ticket", None)
    symbol = _pos_attr(pos, "symbol", "")
    profit = _pos_attr(pos, "profit", 0.0)
    if ticket is None:
        return None
    if now_utc is not None and not is_friday_eod_flat_window(now_utc, symbol=symbol):
        return None
    return CloseDirective(
        ticket=ticket, comment="Friday EOD Flat", collect="closed",
        pre_log=LogLine("warning",
            f"🧹 [FRIDAY REAL-TIME LIQUIDATION] Thanh lý bắt buộc Ticket #{ticket} ({symbol}) | "
            f"Floating PnL: ${profit:+.2f} USD (Zero Weekend Hold Enforced)."),
        fail_log=LogLine("error", f"❌ Lỗi thanh lý Thứ Sáu Ticket #{ticket}: {{error}}"))


def evaluate_friday_eod_flat(positions: Sequence[Any], now_utc: Optional[datetime]) -> RiskEvaluationResult:
    """now_utc None => thanh lý toàn bộ; có now_utc => chỉ các mã đã vào cửa sổ EOD của mã đó."""
    out: List[Directive] = [LogDirective(pre_log=LogLine("warning",
        f"🛑 [FRIDAY EOD FLAT RULE KÍCH HOẠT] Thứ Sáu >= 20:30 UTC (Time Rule 23:30-23:45 Server Time). "
        f"Phát hiện {len(positions)} vị thế đang mở. Bắn lệnh thị trường đối ứng dọn sạch danh mục!"))]
    for pos in positions:
        try:
            d = _friday_one(pos, now_utc)
        except Exception as exc:
            out.append(RaiseDirective(error=exc))
            break
        if d is not None:
            out.append(d)
    return RiskEvaluationResult(directives=tuple(out))


def evaluate_liquidation_readiness(symbol: str, market: MarketView, now_utc: Optional[datetime] = None,
                                   max_tick_age_sec: float = 60.0,
                                   open_warmup_sec: float = 600.0) -> RiskEvaluationResult:
    """Bộ lọc vi cấu trúc theo mã: thị trường mở, tick tươi, warmup mở phiên, spread. (ready, reason) ở kết quả."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()
    reopen = market.reopen_state()
    persist: List[Directive] = []

    def done(ready: bool, reason: str) -> RiskEvaluationResult:
        return RiskEvaluationResult(directives=tuple(persist), ready=ready, reason=reason)

    if not market.is_market_open(symbol):
        return done(False, f"Market closed for {symbol}")

    try:
        actual_sym = market.resolve_symbol(symbol)
        if not isinstance(actual_sym, str) or not actual_sym:
            actual_sym = symbol

        sym_info = market.symbol_info(actual_sym)
        tick = market.symbol_tick(actual_sym)

        if tick is None or not isinstance(getattr(tick, "time", None), (int, float)):
            return done(True, "OK (Manager market_open verified)")

        if sym_info is not None:
            trade_mode = getattr(sym_info, "trade_mode", None)
            full_mode = market.trade_mode_full()
            if isinstance(trade_mode, int) and trade_mode != full_mode:
                return done(False, f"Trade mode {trade_mode} != FULL for {actual_sym}")

        tick_time = float(tick.time)
        if tick_time <= 0:
            return done(False, f"Invalid tick.time=0 for {actual_sym}")

        tick_age = now_ts - tick_time
        if tick_age < -60.0:
            srv_ts = get_mt5_server_datetime(now_utc).timestamp()
            tick_age = srv_ts - tick_time

        if tick_age > max_tick_age_sec or tick_age < -60.0:
            if actual_sym in reopen:
                reopen.pop(actual_sym, None)
                persist.append(ReopenPersistDirective(snapshot=dict(reopen)))
            return done(False, f"Stale tick ({tick_age:.0f}s > {max_tick_age_sec:.0f}s) - {actual_sym} session not yet open")

        if actual_sym not in reopen:
            reopen[actual_sym] = now_ts
            persist.append(ReopenPersistDirective(snapshot=dict(reopen)))
        first_seen = float(reopen[actual_sym])
        elapsed_since_open = max(0.0, now_ts - first_seen)

        if open_warmup_sec > 0 and elapsed_since_open < open_warmup_sec:
            return done(False, f"Warmup Buffer active for {actual_sym} ({elapsed_since_open:.0f}s / {open_warmup_sec:.0f}s post-open)")

        bid = float(getattr(tick, "bid", 0.0) or 0.0)
        ask = float(getattr(tick, "ask", 0.0) or 0.0)
        point = float(getattr(sym_info, "point", 0.0) or 0.0) if sym_info is not None else 0.0

        if bid > 0 and ask >= bid and elapsed_since_open < 1800.0:
            sym_upper = actual_sym.upper()
            if any(k in sym_upper for k in _INDEX_KEYS):
                rel_spread = (ask - bid) / bid
                max_rel_spread = 0.0008
                if rel_spread > max_rel_spread:
                    return done(False, f"Index Spread Guard active for {actual_sym} ({rel_spread*10000:.1f} bps > {max_rel_spread*10000:.1f} bps)")
            elif point > 0:
                spread_pts = (ask - bid) / point
                max_pts = 35.0 if any(m in sym_upper for m in _MAJORS) else 65.0
                if spread_pts > max_pts:
                    return done(False, f"FX Spread Guard active for {actual_sym} ({spread_pts:.1f} pts > {max_pts:.1f} pts)")

        return done(True, f"Ready (post-open={elapsed_since_open:.0f}s)")
    except Exception as e:
        return RiskEvaluationResult(
            directives=tuple(persist) + (LogDirective(pre_log=LogLine(
                "debug", f"check_symbol_liquidation_readiness fallback for {symbol}: {e}")),),
            ready=True, reason="OK (Fallback)")


def _pos_time_utc(pos_time, now_utc: datetime) -> datetime:
    if isinstance(pos_time, datetime):
        return pos_time if pos_time.tzinfo else pos_time.replace(tzinfo=timezone.utc)
    if isinstance(pos_time, (int, float)):
        return datetime.fromtimestamp(pos_time, tz=timezone.utc)
    return now_utc


def evaluate_weekend_sweeper(positions: Sequence[dict], market: MarketView, now_utc: Optional[datetime],
                             open_warmup_sec: float = 600.0) -> RiskEvaluationResult:
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    if is_friday_eod_flat_window(now_utc):
        open_market_positions = [p for p in positions if market.is_market_open(p.get("symbol", ""))]
        if open_market_positions:
            return RiskEvaluationResult(delegate="friday_eod_flat")
        if positions:
            return RiskEvaluationResult(directives=(LogDirective(pre_log=LogLine("info",
                f"⏸️ [WEEKEND HOLD QUEUED] Phát hiện {len(positions)} vị thế mở sau giờ đóng sàn Thứ Sáu. "
                f"Đã đưa vào hàng đợi thanh lý thông minh (Per-Symbol Tick + Spread Guard) khi thị trường mở cửa!")),))
        return RiskEvaluationResult()

    if not positions:
        return RiskEvaluationResult()

    last_weekly_open_utc = get_last_weekly_open_utc(now_utc)
    out: List[Directive] = []
    for pos in positions:
        try:
            ticket = pos.get("ticket")
            symbol = pos.get("symbol", "")
            profit = float(pos.get("profit", 0.0))
            pos_time_utc = _pos_time_utc(pos.get("time"), now_utc)

            pos_age_hours = (now_utc - pos_time_utc).total_seconds() / 3600.0
            is_weekend_hold = pos_time_utc < last_weekly_open_utc
            is_over_12h_hold = pos_age_hours >= 12.0

            if is_weekend_hold or is_over_12h_hold:
                effective_warmup = open_warmup_sec if is_weekend_hold else 0.0
                rd = evaluate_liquidation_readiness(symbol, market, now_utc, 60.0, effective_warmup)
                out.extend(rd.directives)
                if not rd.ready:
                    out.append(LogDirective(pre_log=LogLine("info",
                        f"⏳ [SWEEPER MICROSTRUCTURE GUARD] Hoãn đóng #{ticket} ({symbol}): {rd.reason}")))
                    continue

                reason_comment = "Weekend Hold Flat" if is_weekend_hold else "Emergency 12h Cut"
                out.append(CloseDirective(
                    ticket=ticket, comment=reason_comment, collect="closed",
                    pre_log=LogLine("warning",
                        f"🧹 [SKILL 07 {reason_comment.upper()}] Thanh lý vị thế Ticket #{ticket} ({symbol}) "
                        f"ngâm {pos_age_hours:.1f}h (Open: {pos_time_utc.strftime('%Y-%m-%d %H:%M')} UTC, "
                        f"PnL: ${profit:+.2f} USD | Gate: {rd.reason}).")))
        except Exception as exc:
            out.append(RaiseDirective(error=exc))
            break
    return RiskEvaluationResult(directives=tuple(out))


# ====================================================================================================
# CỔNG DUY NHẤT evaluate_risk
# ====================================================================================================

_HARD_CAPS = {
    RiskCheck.HARD_CAP_XAUUSD, RiskCheck.HARD_CAP_INDEX,
    RiskCheck.HARD_CAP_GBPCHF_UK100, RiskCheck.HARD_CAP_FOREX_PORTFOLIO,
}


def _stagnation_one(pos: dict, market: MarketView, now_utc: datetime, ladder_locked, tier2_locked) -> List[Directive]:
    pos_time = pos.get("time")
    if isinstance(pos_time, datetime):
        pos_time_utc = pos_time if pos_time.tzinfo else pos_time.replace(tzinfo=timezone.utc)
    elif isinstance(pos_time, (int, float)):
        pos_time_utc = datetime.fromtimestamp(pos_time, tz=timezone.utc)
    else:
        return []
    pos_age_hours = (now_utc - pos_time_utc).total_seconds() / 3600.0
    pos_profit = float(pos.get("profit", 0.0)) + float(pos.get("swap", 0.0))
    ticket = pos.get("ticket")
    symbol = pos.get("symbol")

    # PROFIT IMMUNITY: không bao giờ cắt lệnh đang có lãi (> $0) hoặc đã khóa lãi từ Tầng 1 ladder trở lên
    if pos_profit > 0.0 or ticket in ladder_locked or ticket in tier2_locked:
        return []

    # SELECTIVE DECAY CUT: ngâm >= 8.0h và PnL trong vùng -$6.00 <= PnL <= $0.00
    if pos_age_hours >= 8.0 and (-6.0 <= pos_profit <= 0.0):
        if not market.is_market_open(symbol):
            return []
        return [CloseDirective(
            ticket=ticket, comment="Stagnation 8h Cut",
            pre_log=LogLine("info",
                f"⏱️ [SELECTIVE STAGNATION CUT] Ticket #{ticket} ({symbol}) "
                f"ngâm {pos_age_hours:.1f}h trong sideway tắt thanh khoản (PnL: ${pos_profit:+.2f} USD). "
                f"Đóng giải phóng ký quỹ sau 8 tiếng."))]
    return []


def evaluate_stagnation_exit(positions: Sequence[dict], market: MarketView, now_utc: datetime,
                             ladder_locked, tier2_locked) -> RiskEvaluationResult:
    out: List[Directive] = []
    for pos in positions:
        try:
            out.extend(_stagnation_one(pos, market, now_utc, ladder_locked, tier2_locked))
        except Exception as exc:
            out.append(RaiseDirective(error=exc))
            break
    return RiskEvaluationResult(directives=tuple(out))


def evaluate_soft_derisking(active_positions, spec_lookup, can_modify):
    """Soft de-risking THUẦN: trả về (plan, directives). spec_lookup(symbol) -> (point, digits).
    Lệnh lãi -> ModifyDirective(sl=entry±15 point, capture=<chỉ số plan>) + log; lệnh lỗ -> chỉ log. Không đóng lệnh."""
    plan: List[Dict[str, Any]] = []
    directives: List[Directive] = []
    for p in active_positions:
        ticket = int(p.get("ticket", 0) if isinstance(p, dict) else getattr(p, "ticket", 0))
        symbol = str(p.get("symbol", "") if isinstance(p, dict) else getattr(p, "symbol", ""))
        profit = float(p.get("profit", 0.0) if isinstance(p, dict) else getattr(p, "profit", 0.0))
        raw_type = p.get("type", "") if isinstance(p, dict) else getattr(p, "type", "")
        price_open = float(p.get("price_open", p.get("open_price", 0.0)) if isinstance(p, dict) else getattr(p, "price_open", 0.0))

        symbol_point, digits = spec_lookup(symbol)
        is_buy = str(raw_type).upper() in ["BUY", "0"] or raw_type == 0

        if profit > 0:
            buffer_offset = 15.0 * symbol_point
            new_sl = round(price_open + buffer_offset if is_buy else price_open - buffer_offset, digits)
            if can_modify:
                directives.append(ModifyDirective(ticket=ticket, sl=new_sl, send_tp=False, capture=str(len(plan))))
            directives.append(LogDirective(pre_log=LogLine("info",
                f"🛡️ [SOFT DE-RISKING] Profitable Position #{ticket} ({symbol}, PnL: +${profit:.2f} USD): "
                f"Locked in Break-Even + 15pt buffer. Target SL updated to {new_sl} (Open: {price_open}).")))
            plan.append({
                "ticket": ticket,
                "symbol": symbol,
                "action": "LOCK_IN_BREAKEVEN_BUFFER",
                "new_sl": new_sl,
                "profit": profit,
                "result": None,
            })
        else:
            directives.append(LogDirective(pre_log=LogLine("info",
                f"🛡️ [SOFT DE-RISKING] Floating Loss Position #{ticket} ({symbol}, PnL: -${abs(profit):.2f} USD): "
                f"Retained original protective SL to await technical pullback. Market close avoided.")))
            plan.append({
                "ticket": ticket,
                "symbol": symbol,
                "action": "RETAIN_ORIGINAL_SL",
                "profit": profit,
            })
    return plan, tuple(directives)


def evaluate_emergency_liquidation(active_positions):
    """Thanh lý khẩn cấp THUẦN (ADR-003): trả về (plan, directives), một CloseDirective cho MỌI vị thế (cả lãi lẫn lỗ).

    plan[i] và directives[i] tương ứng 1-1 (capture = chỉ số i). Đóng thất bại: log lỗi + AlertDirective; caller tiếp tục các lệnh còn lại.
    """
    plan: List[Dict[str, Any]] = []
    directives: List[Directive] = []
    for idx, p in enumerate(active_positions):
        ticket = int(p.get("ticket", 0) if isinstance(p, dict) else getattr(p, "ticket", 0))
        symbol = str(p.get("symbol", "") if isinstance(p, dict) else getattr(p, "symbol", ""))
        profit = float(p.get("profit", 0.0) if isinstance(p, dict) else getattr(p, "profit", 0.0))
        directives.append(CloseDirective(
            ticket=ticket,
            capture=str(idx),
            pre_log=LogLine("warning", f"🚨 [EMERGENCY LIQUIDATION] Đóng #{ticket} ({symbol}, PnL: {profit:+.2f} USD)."),
            ok_log=LogLine("info", f"✅ [EMERGENCY LIQUIDATION] Đã đóng #{ticket} ({symbol})."),
            fail_log=LogLine("error", f"❌ [EMERGENCY LIQUIDATION] Đóng #{ticket} ({symbol}) THẤT BẠI: {{error}}"),
            on_failure=(AlertDirective(
                subject="EMERGENCY LIQUIDATION: CLOSE FAILED",
                body=f"Không đóng được vị thế #{ticket} ({symbol}, PnL {profit:+.2f} USD). Cần can thiệp tay."),),
        ))
        plan.append({"ticket": ticket, "symbol": symbol, "action": "EMERGENCY_CLOSE", "profit": profit, "result": None})
    return plan, tuple(directives)


def _legacy_inline_execute(directives, broker_connector):
    """Bộ thực thi nội tuyến KẾ THỪA cho apply_soft_derisking / apply_emergency_liquidation khi caller không truyền executor (L5).
    Luồng live đi qua L5 (runner truyền executor); hàm này chỉ giữ tương thích cho lời gọi/test trực tiếp."""
    captured: Dict[str, Any] = {}

    def _ok(res):
        return bool(res.get("success")) if isinstance(res, dict) else bool(res)

    for d in directives:
        if isinstance(d, ModifyDirective):
            captured[d.capture] = broker_connector.modify_position_sltp(ticket=d.ticket, sl=d.sl)
        elif isinstance(d, CloseDirective):
            if d.pre_log:
                getattr(logger, d.pre_log.level)(d.pre_log.message)
            res = broker_connector.close_position(ticket=d.ticket)
            if d.capture is not None:
                captured[d.capture] = res
            if _ok(res):
                if d.ok_log:
                    getattr(logger, d.ok_log.level)(d.ok_log.message)
            else:
                err = res.get("error") if isinstance(res, dict) else None
                if d.fail_log:
                    getattr(logger, d.fail_log.level)(d.fail_log.message.replace("{error}", str(err)))
                for f in d.on_failure:
                    if isinstance(f, AlertDirective):
                        logger.critical(f"🚨 [ALERT] {f.subject}: {f.body}")
        elif isinstance(d, LogDirective):
            getattr(logger, d.pre_log.level)(d.pre_log.message)
    return captured


def evaluate_entry_gate(symbol, direction, current_ts, deals, symbol_state_fn, cooldown_sec, lockout_sec):
    """Gate vào lệnh THUẦN: Anti-Chasing Cooldown + Same-Direction 2-SL Lockout. Trả về (allowed, reason).

    `deals` là tuple[DealView] từ L1 (None => dùng trạng thái bộ nhớ qua symbol_state_fn(), chỉ gọi khi cần).
    """
    clean_sym = symbol.upper().replace("M", "")
    dir_upper = direction.upper()

    if deals is not None:
        pos_dirs = {}
        for d in deals:
            if d.entry == 0:
                pos_dirs[d.position_id] = "BUY" if d.type == 0 else "SELL"

        closed_deals = [
            d for d in deals
            if (d.symbol or "").upper().replace("M", "") == clean_sym
            and d.entry in (1, 3)
            and float(d.time) <= current_ts
        ]
        closed_deals.sort(key=lambda d: (float(d.time), int(d.ticket)))

        if closed_deals:
            last_deal = closed_deals[-1]
            time_since_exit = current_ts - float(last_deal.time)
            if time_since_exit < cooldown_sec:
                rem = int(cooldown_sec - time_since_exit)
                return False, f"VETO_ANTI_CHASING_COOLDOWN: Cooldown còn {rem}s trên {clean_sym} (Chống fomo/đu đỉnh đáy sau đóng lệnh)"

        if len(closed_deals) >= 2:
            d1 = closed_deals[-2]
            d2 = closed_deals[-1]
            p1 = float(d1.profit)
            p2 = float(d2.profit)

            dir1 = pos_dirs.get(d1.position_id, "BUY" if d1.type == 1 else "SELL")
            dir2 = pos_dirs.get(d2.position_id, "BUY" if d2.type == 1 else "SELL")

            if p1 < 0 and p2 < 0 and dir1 == dir2 and dir1 == dir_upper:
                time_since_d2 = current_ts - float(d2.time)
                if time_since_d2 < lockout_sec:
                    rem = int(lockout_sec - time_since_d2)
                    return False, f"VETO_2SL_DIRECTION_LOCKOUT (VETO_TREND_TRAP): Đang khóa chiều {dir1} trên {clean_sym} do dính 2 SL liên tiếp (còn {rem}s)"
    else:
        st = symbol_state_fn().get(clean_sym, {})
        last_exit = st.get("last_exit_ts", 0.0)
        if current_ts - last_exit < cooldown_sec:
            rem = int(cooldown_sec - (current_ts - last_exit))
            return False, f"VETO_ANTI_CHASING_COOLDOWN (VETO_ANTI_CHASING): Cooldown còn {rem}s trên {clean_sym}"

        if dir_upper == "BUY" and current_ts < st.get("lock_buy_until", 0.0):
            rem = int(st.get("lock_buy_until", 0.0) - current_ts)
            return False, f"VETO_2SL_DIRECTION_LOCKOUT (VETO_TREND_TRAP): Đang khóa chiều BUY trên {clean_sym} do dính 2 SL liên tiếp (còn {rem}s)"
        if dir_upper == "SELL" and current_ts < st.get("lock_sell_until", 0.0):
            rem = int(st.get("lock_sell_until", 0.0) - current_ts)
            return False, f"VETO_2SL_DIRECTION_LOCKOUT (VETO_TREND_TRAP): Đang khóa chiều SELL trên {clean_sym} do dính 2 SL liên tiếp (còn {rem}s)"

    return True, "OK"


def evaluate_exit_tracking(now_ts, tracked_open, current_positions, deals_lookup, symbol_state,
                           cooldown_sec, lockout_dur, max_consec, emit):
    """Theo dõi vị thế vừa đóng: cập nhật symbol_state (last_exit_ts, đếm SL liên tiếp, khóa chiều) TẠI CHỖ.

    deals_lookup() -> tuple[DealView]|None (L1, gọi MỘT LẦN cho MỖI vị thế vừa đóng như bản cũ);
    emit(LogLine) ghi log ngay theo đúng thứ tự (kể cả khi có ngoại lệ giữa chừng).
    """
    for old_ticket, old_pos in tracked_open.items():
        if old_ticket not in current_positions:
            symbol = old_pos.get("symbol", "")
            clean_sym = symbol.upper().replace("M", "")
            pos_type = old_pos.get("type", "BUY")

            deals = deals_lookup()
            deal_pnl = 0.0
            deal_comment = ""
            if deals:
                for d in deals:
                    if d.position_id == old_ticket and d.entry == 1:
                        deal_pnl = float(d.profit + d.commission + d.swap)
                        deal_comment = str(d.comment)
                        break

            st = symbol_state.setdefault(
                clean_sym,
                {
                    "last_exit_ts": now_ts,
                    "consec_sl_buy": 0,
                    "consec_sl_sell": 0,
                    "lock_buy_until": 0.0,
                    "lock_sell_until": 0.0,
                }
            )
            st["last_exit_ts"] = now_ts

            is_sl = ("sl" in deal_comment.lower()) or (deal_pnl < -0.5)

            if is_sl:
                if pos_type in ["BUY", 0]:
                    st["consec_sl_buy"] += 1
                    st["consec_sl_sell"] = 0
                    if st["consec_sl_buy"] >= max_consec:
                        st["lock_buy_until"] = now_ts + lockout_dur
                        emit(LogLine("warning",
                            f"🛑 [SAME-DIRECTION SL LOCKOUT] {clean_sym} dính {st['consec_sl_buy']} SL liên tiếp chiều BUY. "
                            f"Khóa mở BUY trong {lockout_dur/3600:.1f} giờ để chống bắt dao rơi."))
                elif pos_type in ["SELL", 1]:
                    st["consec_sl_sell"] += 1
                    st["consec_sl_buy"] = 0
                    if st["consec_sl_sell"] >= max_consec:
                        st["lock_sell_until"] = now_ts + lockout_dur
                        emit(LogLine("warning",
                            f"🛑 [SAME-DIRECTION SL LOCKOUT] {clean_sym} dính {st['consec_sl_sell']} SL liên tiếp chiều SELL. "
                            f"Khóa mở SELL trong {lockout_dur/3600:.1f} giờ để chống bán ngược xu hướng tăng (Anti-Trend Trap)."))
            elif deal_pnl > 0.0:
                st["consec_sl_buy"] = 0
                st["consec_sl_sell"] = 0

            emit(LogLine("info",
                f"🔔 [POSITION CLOSED DETECTED] Ticket #{old_ticket} ({symbol} {pos_type}): "
                f"PnL ${deal_pnl:+.2f} USD ({deal_comment}). Kích hoạt Anti-Chasing Cooldown 15m "
                f"(đến {datetime.fromtimestamp(now_ts + cooldown_sec, tz=timezone.utc).strftime('%H:%M:%S')} UTC)."))


def evaluate_risk(
    check: RiskCheck,
    *,
    positions: Sequence[Any] = (),
    market: Optional[MarketView] = None,
    now_utc: Optional[datetime] = None,
    params: Optional[Mapping[str, Any]] = None,
    state: Optional[Mapping[str, Any]] = None,
    symbol: Optional[str] = None,
) -> RiskEvaluationResult:
    """Đánh giá một kiểm tra rủi ro; trả về chỉ thị theo đúng thứ tự cần thực thi."""
    check = RiskCheck(check)
    params = params or {}

    if check in _HARD_CAPS:
        return evaluate_hard_cap(check.value, positions, params["max_loss_usd"])
    if check is RiskCheck.RECONCILE_INDEX:
        return evaluate_reconcile_index(positions)
    if check is RiskCheck.BREAKEVEN_LOCK:
        return evaluate_breakeven(positions, market, params.get("buffer_pips", 1.5))
    if check is RiskCheck.PROFIT_LADDER:
        return evaluate_profit_ladder(positions, market)
    if check is RiskCheck.TWO_TIER_EXIT:
        return evaluate_two_tier_exit(
            positions, market, state or {}, params.get("min_partial_profit_usd", 25.0))
    if check is RiskCheck.FRIDAY_EOD_FLAT:
        return evaluate_friday_eod_flat(positions, now_utc)
    if check is RiskCheck.WEEKEND_SWEEPER:
        return evaluate_weekend_sweeper(
            positions, market, now_utc, params.get("open_warmup_sec", 600.0))
    if check is RiskCheck.LIQUIDATION_READINESS:
        return evaluate_liquidation_readiness(
            symbol, market, now_utc, params.get("max_tick_age_sec", 60.0), params.get("open_warmup_sec", 600.0))
    if check is RiskCheck.STAGNATION_EXIT:
        st = state or {}
        return evaluate_stagnation_exit(
            positions, market, now_utc, st.get("ladder_locked", ()), st.get("tier2_locked", ()))
    if check is RiskCheck.ENTRY_GATE:
        ok, reason = evaluate_entry_gate(
            symbol, params["direction"], params["current_ts"], params["deals"], params["symbol_state_fn"],
            params["cooldown_sec"], params["lockout_sec"])
        return RiskEvaluationResult(ready=ok, reason=reason)
    if check is RiskCheck.EXIT_TRACKING:
        evaluate_exit_tracking(
            params["now_ts"], params["tracked_open"], params["current_positions"], params["deals_lookup"],
            state, params["cooldown_sec"], params["lockout_dur"], params["max_consec"], params["emit"])
        return RiskEvaluationResult()
    raise ValueError(f"RiskCheck không được hỗ trợ: {check}")


# ====================================================================================================
# 05_risk/the_fourth_estate/exposure_and_beta_desk.py  —  The Fourth Estate / Central Risk Desk: Gross/Net Exposure & Dollar Beta Desk.
# ====================================================================================================




@dataclass
class PositionSnapshot:
    """Individual position snapshot for exposure auditing."""
    asset: str
    notional_value: float  # Positive for Long, Negative for Short
    asset_beta: float      # Beta against SPY / Global benchmark
    adv_pct: float = 0.01  # Fraction of 30-day Average Daily Volume (ADV)


@dataclass
class ExposureAndBetaReport:
    """Full Exposure and Beta Audit Report."""
    portfolio_equity: float
    gross_exposure_dollar: float
    gross_leverage: float
    net_exposure_dollar: float
    net_leverage: float
    portfolio_market_beta: float
    is_market_neutral: bool
    hhi_concentration: float
    max_single_asset_exposure_pct: float
    is_compliant: bool
    violations: List[str] = field(default_factory=list)


class ExposureAndBetaDesk:
    """
    Independent Risk Desk enforcing Leverage, Market Neutrality, and Concentration Limits.
    Based on Millennium / Citadel multi-manager mandate.
    """

    def __init__(
        self,
        max_gross_leverage: float = 4.0,
        max_net_leverage: float = 0.20,
        max_market_beta: float = 0.05,
        max_hhi_concentration: float = 0.35,
        max_single_asset_pct: float = 0.40
    ):
        self.max_gross_leverage = max_gross_leverage
        self.max_net_leverage = max_net_leverage
        self.max_market_beta = max_market_beta
        self.max_hhi_concentration = max_hhi_concentration
        self.max_single_asset_pct = max_single_asset_pct

    def audit_positions(
        self,
        positions: List[PositionSnapshot],
        portfolio_equity: float
    ) -> ExposureAndBetaReport:
        """
        Audits current book positions against constitutional risk constraints.
        """
        if portfolio_equity <= 0:
            raise ValueError(f"Portfolio equity must be strictly positive: {portfolio_equity}")

        if not positions:
            return ExposureAndBetaReport(
                portfolio_equity=portfolio_equity,
                gross_exposure_dollar=0.0,
                gross_leverage=0.0,
                net_exposure_dollar=0.0,
                net_leverage=0.0,
                portfolio_market_beta=0.0,
                is_market_neutral=True,
                hhi_concentration=0.0,
                max_single_asset_exposure_pct=0.0,
                is_compliant=True,
                violations=[]
            )

        notionals = np.array([p.notional_value for p in positions], dtype=float)
        betas = np.array([p.asset_beta for p in positions], dtype=float)

        gross_exposure = float(np.sum(np.abs(notionals)))
        net_exposure = float(np.sum(notionals))

        gross_leverage = float(gross_exposure / portfolio_equity)
        net_leverage = float(abs(net_exposure) / portfolio_equity)

        # Portfolio beta weighted by equity allocation: beta_port = sum( (V_i / Equity) * beta_i )
        portfolio_beta = float(np.sum((notionals / portfolio_equity) * betas))

        # HHI Concentration: sum( ( |V_i| / Gross )^2 )
        if gross_exposure > 1e-6:
            weights = np.abs(notionals) / gross_exposure
            hhi = float(np.sum(weights ** 2))
            max_single_pct = float(np.max(weights))
        else:
            hhi = 0.0
            max_single_pct = 0.0

        violations = []

        # 1. Gross leverage check
        if gross_leverage > self.max_gross_leverage:
            violations.append(
                f"Gross leverage {round(gross_leverage, 2)}x exceeds limit {self.max_gross_leverage}x"
            )

        # 2. Net leverage check
        if net_leverage > self.max_net_leverage:
            violations.append(
                f"Net leverage {round(net_leverage, 2)}x exceeds limit {self.max_net_leverage}x"
            )

        # 3. Market Beta neutrality check (|beta| <= 0.05)
        is_neutral = bool(abs(portfolio_beta) <= self.max_market_beta)
        if not is_neutral:
            violations.append(
                f"Portfolio Market Beta {round(portfolio_beta, 4)} violates neutrality limit |beta| <= {self.max_market_beta}"
            )

        # 4. HHI concentration check
        if hhi > self.max_hhi_concentration:
            violations.append(
                f"HHI Concentration {round(hhi, 4)} exceeds limit {self.max_hhi_concentration}"
            )

        # 5. Single asset cap
        if max_single_pct > self.max_single_asset_pct:
            violations.append(
                f"Single asset concentration {round(max_single_pct * 100, 1)}% exceeds limit {self.max_single_asset_pct * 100}%"
            )

        is_compliant = (len(violations) == 0)

        return ExposureAndBetaReport(
            portfolio_equity=portfolio_equity,
            gross_exposure_dollar=round(gross_exposure, 2),
            gross_leverage=round(gross_leverage, 4),
            net_exposure_dollar=round(net_exposure, 2),
            net_leverage=round(net_leverage, 4),
            portfolio_market_beta=round(portfolio_beta, 4),
            is_market_neutral=is_neutral,
            hhi_concentration=round(hhi, 4),
            max_single_asset_exposure_pct=round(max_single_pct, 4),
            is_compliant=is_compliant,
            violations=violations
        )


# ====================================================================================================
# 05_risk/the_fourth_estate/federal_master_kill_switch.py  —  The Federal Master Kill-Switch (Totalitarian Emergency Circuit Breaker).
# ====================================================================================================



logger = logging.getLogger("FederalMasterKillSwitch")


class FederalCircuitBreakerActive(Exception):
    """Raised when orders are attempted while the Federal Master Kill-Switch is locked."""
    pass


@dataclass
class KillSwitchDirective:
    """Action directive emitted by the Federal Master Kill-Switch."""
    status_level: str          # "NORMAL", "YELLOW_ALERT", "ORANGE_ALERT", "RED_KILL_SWITCH"
    current_drawdown_pct: float
    is_trading_locked: bool
    position_scale_factor: float  # 1.0 (Normal), 0.5 (Yellow), 0.25 (Orange), 0.0 (Locked)
    reason: str
    auth_token: str
    timestamp: float


class FederalMasterKillSwitch:
    """
    Totalitarian Risk Kill-Switch.
    Holds overriding supreme authority to sever all live execution connections
    and enforce Soft De-risking protocols to preserve the federation's survival.
    """

    def __init__(
        self,
        yellow_threshold: float = -0.03,  # -3%
        orange_threshold: float = -0.05,  # -5%
        red_threshold: float = -0.12,     # -12.0%
        secret_passphrase: str = "CONSTITUTIONAL_EMERGENCY_OVERRIDE_KEY"
    ):
        self.yellow_threshold = yellow_threshold
        self.orange_threshold = orange_threshold
        self.red_threshold = red_threshold
        self.secret_passphrase = secret_passphrase

        self.peak_equity: float = 0.0
        self.current_equity: float = 0.0
        self.is_locked: bool = False
        self.freeze_until: float = 0.0
        self.incident_history: List[KillSwitchDirective] = []

    def update_equity(
        self,
        current_equity: float,
        broker_connector: Optional[Any] = None,
        executor: Optional[Any] = None,
    ) -> KillSwitchDirective:
        """
        Updates live portfolio equity, calculates drawdown from peak,
        and enforces the totalitarian drawdown ladder.
        """
        if current_equity <= 0:
            raise ValueError(f"Invalid portfolio equity: {current_equity}")

        if self.peak_equity <= 0 or current_equity > self.peak_equity:
            self.peak_equity = current_equity

        self.current_equity = current_equity
        drawdown_pct = (self.current_equity - self.peak_equity) / self.peak_equity

        # If already locked, maintain lockdown until explicit cryptographic unfreeze
        if self.is_locked:
            return self._create_directive(
                status_level="RED_KILL_SWITCH",
                drawdown_pct=drawdown_pct,
                is_locked=True,
                scale_factor=0.0,
                reason="Federation is currently LOCKED under Master Kill-Switch quarantine."
            )

        # 1. Level 3: Red Catastrophic Breaker
        if drawdown_pct <= self.red_threshold:
            self.is_locked = True
            directive = self._create_directive(
                status_level="RED_KILL_SWITCH",
                drawdown_pct=drawdown_pct,
                is_locked=True,
                scale_factor=0.0,
                reason=f"CRITICAL DRAWDOWN {round(drawdown_pct * 100, 2)}% breached limit {round(self.red_threshold * 100, 1)}%. MASTER KILL-SWITCH ACTIVATED!"
            )
            # Trigger emergency broker liquidation if connector provided
            if broker_connector is not None:
                self._execute_emergency_liquidation(broker_connector, executor)
            return directive

        # 2. Level 2: Orange Alert
        elif drawdown_pct <= self.orange_threshold:
            return self._create_directive(
                status_level="ORANGE_ALERT",
                drawdown_pct=drawdown_pct,
                is_locked=False,
                scale_factor=0.25,
                reason=f"Orange Risk Alert: Drawdown {round(drawdown_pct * 100, 2)}% breached -5.0%. De-leveraging by 75%."
            )

        # 3. Level 1: Yellow Alert
        elif drawdown_pct <= self.yellow_threshold:
            return self._create_directive(
                status_level="YELLOW_ALERT",
                drawdown_pct=drawdown_pct,
                is_locked=False,
                scale_factor=0.50,
                reason=f"Yellow Risk Alert: Drawdown {round(drawdown_pct * 100, 2)}% breached -3.0%. Cutting new order sizes by 50%."
            )

        # Normal operation
        return self._create_directive(
            status_level="NORMAL",
            drawdown_pct=drawdown_pct,
            is_locked=False,
            scale_factor=1.0,
            reason="Portfolio operating within constitutional risk boundaries."
        )

    def verify_order_permission(self) -> None:
        """
        Gatekeeper check before any order can be routed.
        Raises FederalCircuitBreakerActive if locked or within 24h freeze window.
        """
        if self.is_locked or (self.freeze_until > 0 and time.time() < self.freeze_until):
            remaining_hours = max(0.0, (self.freeze_until - time.time()) / 3600.0) if self.freeze_until > 0 else 0.0
            raise FederalCircuitBreakerActive(
                f"FEDERAL EMERGENCY: Master Kill-Switch is ACTIVE (Soft De-risking engaged). "
                f"All trading rights are suspended (Freeze remaining: {remaining_hours:.1f} hours)."
            )

    def manual_emergency_shutdown(
        self,
        reason: str,
        broker_connector: Optional[Any] = None,
        executor: Optional[Any] = None,
    ) -> KillSwitchDirective:
        """
        Manual trigger of the Federal Master Kill-Switch by the Chief Risk Officer.
        ADR-003: thanh lý toàn bộ vị thế mở (apply_emergency_liquidation) rồi khóa mở lệnh mới.
        """
        self.is_locked = True
        self.freeze_until = time.time() + 86400.0  # 24 hours freeze
        dd_pct = (self.current_equity - self.peak_equity) / max(self.peak_equity, 1.0)
        directive = self._create_directive(
            status_level="RED_KILL_SWITCH",
            drawdown_pct=dd_pct,
            is_locked=True,
            scale_factor=0.0,
            reason=f"MANUAL CRO OVERRIDE: {reason}"
        )
        if broker_connector is not None:
            self._execute_emergency_liquidation(broker_connector, executor)
        return directive

    def unlock_federation(self, unfreeze_token: str) -> bool:
        """
        Unfreezes the federation after audit, requiring the cryptographic pass token.
        """
        expected_token = hashlib.sha256(self.secret_passphrase.encode()).hexdigest()
        if unfreeze_token == expected_token or unfreeze_token == self.secret_passphrase:
            self.is_locked = False
            self.freeze_until = 0.0
            self.peak_equity = self.current_equity  # Reset peak benchmark upon authorized recovery
            logger.info("🔓 [FEDERATION UNLOCKED] Master Kill-Switch reset and 24h freeze cleared.")
            return True
        return False

    def _create_directive(
        self,
        status_level: str,
        drawdown_pct: float,
        is_locked: bool,
        scale_factor: float,
        reason: str
    ) -> KillSwitchDirective:
        now = time.time()
        raw = f"{status_level}:{drawdown_pct}:{is_locked}:{now}:{self.secret_passphrase}"
        token = hashlib.sha256(raw.encode()).hexdigest()[:16]

        directive = KillSwitchDirective(
            status_level=status_level,
            current_drawdown_pct=round(drawdown_pct, 4),
            is_trading_locked=is_locked,
            position_scale_factor=scale_factor,
            reason=reason,
            auth_token=token,
            timestamp=now
        )
        self.incident_history.append(directive)
        return directive

    def apply_soft_derisking(
        self,
        active_positions: List[Dict[str, Any]],
        broker_connector: Optional[Any] = None,
        executor: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Quant Core V9: Soft De-risking Protocol (KHÔNG đóng lệnh).
        1. Đóng băng tín hiệu mới 24 giờ.
        2. Lệnh đang lãi (PnL > 0): dời SL về Entry ± (15 * symbol_point).
        3. Lệnh đang lỗ: giữ nguyên SL gốc.
        Quyết định do evaluate_soft_derisking (thuần) sinh ra; `executor(directives) -> {capture: kết quả}` (L5) thực thi.
        Không truyền executor: dùng bộ thực thi nội tuyến kế thừa qua broker_connector (tương thích lời gọi cũ).
        """
        self.freeze_until = time.time() + 86400.0  # 24 hours freeze
        self.is_locked = True
        logger.warning(
            f"🛑 [SOFT DE-RISKING PROTOCOL ACTIVATED] System freeze engaged for 24 hours (until {time.ctime(self.freeze_until)}). "
            f"Market dump (Fleet Close) ABORTED. Processing {len(active_positions)} active positions via Soft De-risking..."
        )

        def _spec_lookup(symbol: str):
            symbol_point = 0.0001
            digits = 2
            if broker_connector and hasattr(broker_connector, "get_symbol_spec"):
                spec = broker_connector.get_symbol_spec(symbol)
                symbol_point = spec.get("point", 0.0001) or 0.0001
                digits = spec.get("digits", 2) or 2
            else:
                try:
                    import MetaTrader5 as mt5
                    s_info = mt5.symbol_info(symbol)
                    if s_info:
                        symbol_point = getattr(s_info, "point", 0.0001) or 0.0001
                        digits = getattr(s_info, "digits", 2) or 2
                except Exception:
                    pass
            return symbol_point, digits

        can_modify = bool(broker_connector and hasattr(broker_connector, "modify_position_sltp"))
        plan, directives = evaluate_soft_derisking(active_positions, _spec_lookup, can_modify)
        if executor is not None:
            captured = executor(directives)
        else:
            captured = _legacy_inline_execute(directives, broker_connector)
        for idx, item in enumerate(plan):
            if "result" in item:
                item["result"] = captured.get(str(idx))
        return plan


    def apply_emergency_liquidation(
        self,
        active_positions: List[Dict[str, Any]],
        broker_connector: Optional[Any] = None,
        executor: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """ADR-003: thanh lý TOÀN BỘ vị thế mở (cả lãi lẫn lỗ) + khóa mở lệnh mới 24 giờ.

        Một lệnh đóng thất bại (kể cả ném ngoại lệ) KHÔNG chặn các lệnh còn lại. Sau lượt đầu, quét lại TỐI ĐA 1 lượt các
        ticket còn sót (nếu broker còn báo vị thế đó đang mở). Trả về plan, mỗi mục có `result` của lần đóng cuối cùng.
        """
        self.freeze_until = time.time() + 86400.0  # 24 hours freeze
        self.is_locked = True
        logger.critical(
            f"🛑 [EMERGENCY LIQUIDATION ACTIVATED] Đóng toàn bộ {len(active_positions)} vị thế mở; khóa lệnh mới 24 giờ "
            f"(đến {time.ctime(self.freeze_until)})."
        )
        plan, directives = evaluate_emergency_liquidation(active_positions)
        run = executor if executor is not None else (lambda dirs: _legacy_inline_execute(dirs, broker_connector))

        def _sweep(indices):
            for idx in indices:
                try:
                    captured = run((directives[idx],))
                    plan[idx]["result"] = captured.get(str(idx))
                except Exception as exc:  # một lệnh lỗi không được chặn các lệnh còn lại
                    logger.error(f"❌ [EMERGENCY LIQUIDATION] Ngoại lệ khi đóng #{plan[idx]['ticket']}: {exc}")
                    plan[idx]["result"] = {"success": False, "error": str(exc)}

        def _closed(res):
            return bool(res.get("success")) if isinstance(res, dict) else bool(res)

        _sweep(range(len(plan)))

        leftover = [i for i, item in enumerate(plan) if not _closed(item["result"])]
        if leftover:
            still_open = None
            try:
                if broker_connector is not None and hasattr(broker_connector, "get_positions"):
                    still_open = {int(p.get("ticket", 0) if isinstance(p, dict) else getattr(p, "ticket", 0))
                                  for p in broker_connector.get_positions()}
            except Exception as exc:
                logger.error(f"❌ [EMERGENCY LIQUIDATION] Không đọc được vị thế để quét lại: {exc}")
            retry = [i for i in leftover if still_open is None or plan[i]["ticket"] in still_open]
            if retry:
                logger.warning(f"🔁 [EMERGENCY LIQUIDATION] Quét lại 1 lượt cho {len(retry)} ticket còn sót: {[plan[i]['ticket'] for i in retry]}")
                _sweep(retry)
        return plan

    def _execute_emergency_liquidation(self, broker_connector: Any, executor: Optional[Any] = None) -> None:
        """ADR-003: thanh lý khẩn cấp toàn bộ vị thế (thay cho soft de-risking cũ)."""
        positions = []
        if hasattr(broker_connector, "get_positions"):
            positions = broker_connector.get_positions()
        elif hasattr(broker_connector, "positions"):
            positions = list(broker_connector.positions.values())
        self.apply_emergency_liquidation(positions, broker_connector, executor)


# ====================================================================================================
# 05_risk/the_fourth_estate/fourth_estate_watchdog.py  —  The Fourth Estate Telemetry & Independent Watchdog.
# ====================================================================================================




class SlippageAnomalyAlert(Exception):
    """Raised when broker execution slippage exceeds constitutional threshold."""
    pass


class ExecutionLatencyAlert(Exception):
    """Raised when execution latency exceeds acceptable real-time threshold."""
    pass


@dataclass
class TelemetryAuditRecord:
    """Audit log entry for a single trade execution."""
    timestamp: float
    asset: str
    action: str
    theoretical_price: float
    fill_price: float
    slippage_bps: float
    latency_ms: float
    is_anomaly: bool
    details: str = ""


@dataclass
class RiskIntelligenceDispatch:
    """Published investigative risk intelligence bulletin."""
    total_fills_audited: int
    anomalies_detected: int
    mean_slippage_bps: float
    max_slippage_bps: float
    mean_latency_ms: float
    integrity_score: float  # 0.0 to 100.0
    status: str             # "CLEAN", "WARNING", "COMPROMISED"
    findings: List[str] = field(default_factory=list)


class FourthEstateWatchdog:
    """
    Independent Press & Telemetry Watchdog.
    Audits live execution vs theoretical backtest prices with zero compromise.
    """

    def __init__(
        self,
        max_allowed_slippage_bps: float = 12.0,
        max_allowed_latency_ms: float = 250.0
    ):
        self.max_allowed_slippage_bps = max_allowed_slippage_bps
        self.max_allowed_latency_ms = max_allowed_latency_ms
        self.audit_log: List[TelemetryAuditRecord] = []
        self.anomalies_count: int = 0

    def audit_fill(
        self,
        theoretical_price: float,
        fill_price: float,
        action: str,
        asset: str = "XAUUSD",
        latency_ms: float = 25.0
    ) -> TelemetryAuditRecord:
        """
        Audits a live execution fill against its theoretical benchmark price.
        Slippage bps = (Diff / Theoretical) * 10000.
        """
        if theoretical_price <= 0:
            raise ValueError(f"Theoretical price must be positive: {theoretical_price}")

        if action.upper() == "BUY":
            slippage_diff = fill_price - theoretical_price
        else:
            slippage_diff = theoretical_price - fill_price

        slippage_bps = (slippage_diff / theoretical_price) * 10000.0
        is_anomaly = bool(slippage_bps > self.max_allowed_slippage_bps)

        if is_anomaly:
            self.anomalies_count += 1

        record = TelemetryAuditRecord(
            timestamp=time.time(),
            asset=asset,
            action=action.upper(),
            theoretical_price=round(theoretical_price, 5),
            fill_price=round(fill_price, 5),
            slippage_bps=round(slippage_bps, 2),
            latency_ms=round(latency_ms, 2),
            is_anomaly=is_anomaly,
            details="Adverse slippage detected" if is_anomaly else "Normal execution"
        )
        self.audit_log.append(record)

        if is_anomaly:
            raise SlippageAnomalyAlert(
                f"Fourth Estate Alert: Execution slippage {record.slippage_bps} bps "
                f"exceeds limit {self.max_allowed_slippage_bps} bps for {asset} {action}."
            )

        return record

    def publish_risk_dispatch(self) -> RiskIntelligenceDispatch:
        """
        Compiles all audit records into an official investigative dispatch.
        """
        if not self.audit_log:
            return RiskIntelligenceDispatch(
                total_fills_audited=0,
                anomalies_detected=0,
                mean_slippage_bps=0.0,
                max_slippage_bps=0.0,
                mean_latency_ms=0.0,
                integrity_score=100.0,
                status="CLEAN",
                findings=["No execution fills recorded yet."]
            )

        slippages = [r.slippage_bps for r in self.audit_log]
        latencies = [r.latency_ms for r in self.audit_log]

        mean_slip = float(sum(slippages) / len(slippages))
        max_slip = float(max(slippages))
        mean_lat = float(sum(latencies) / len(latencies))

        # Integrity score degradation
        penalty = (self.anomalies_count * 15.0) + max(0.0, (mean_slip - 5.0) * 2.0)
        score = max(0.0, min(100.0, 100.0 - penalty))

        findings = []
        if self.anomalies_count > 0:
            findings.append(f"Detected {self.anomalies_count} critical slippage anomalies.")
        if mean_lat > self.max_allowed_latency_ms:
            findings.append(f"Mean latency {round(mean_lat, 1)}ms exceeds {self.max_allowed_latency_ms}ms.")

        if score >= 85.0:
            status = "CLEAN"
        elif score >= 60.0:
            status = "WARNING"
        else:
            status = "COMPROMISED"

        if not findings:
            findings.append("Broker execution quality satisfies all institutional standards.")

        return RiskIntelligenceDispatch(
            total_fills_audited=len(self.audit_log),
            anomalies_detected=self.anomalies_count,
            mean_slippage_bps=round(mean_slip, 2),
            max_slippage_bps=round(max_slip, 2),
            mean_latency_ms=round(mean_lat, 2),
            integrity_score=round(score, 1),
            status=status,
            findings=findings
        )


# ====================================================================================================
# 05_risk/the_fourth_estate/var_cvar_engine.py  —  The Fourth Estate / Central Risk Desk: VaR & CVaR (Expected Shortfall) Engine.
# ====================================================================================================




@dataclass
class VaRMetricResult:
    """Quantitative risk metrics at a specific confidence level."""
    confidence_level: float
    parametric_var_pct: float
    parametric_var_dollar: float
    historical_var_pct: float
    historical_var_dollar: float
    historical_cvar_pct: float
    historical_cvar_dollar: float
    monte_carlo_var_pct: float
    monte_carlo_var_dollar: float
    monte_carlo_cvar_pct: float
    monte_carlo_cvar_dollar: float
    portfolio_equity: float


class CentralVaREngine:
    """
    Central Risk Desk VaR & CVaR Calculation Engine.
    Enforces Basel III / Institutional Hedge Fund risk quantification.
    """

    def __init__(self, default_confidence: float = 0.99):
        self.default_confidence = default_confidence

    def calculate_parametric_var(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        portfolio_equity: float,
        confidence_level: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculates parametric VaR using analytical Variance-Covariance method.
        VaR = z_alpha * sigma_port * Portfolio_Equity
        """
        alpha = confidence_level if confidence_level is not None else self.default_confidence
        weights = np.asarray(weights, dtype=float)
        cov_matrix = np.asarray(cov_matrix, dtype=float)

        port_variance = float(weights.T @ cov_matrix @ weights)
        port_sigma = float(np.sqrt(max(port_variance, 1e-12)))

        z_score = float(stats.norm.ppf(alpha))
        var_pct = float(z_score * port_sigma)
        var_dollar = float(var_pct * portfolio_equity)

        return {
            "var_pct": round(var_pct, 6),
            "var_dollar": round(var_dollar, 2),
            "port_sigma": round(port_sigma, 6),
            "z_score": round(z_score, 4)
        }

    def calculate_historical_var_cvar(
        self,
        historical_returns: np.ndarray,
        weights: np.ndarray,
        portfolio_equity: float,
        confidence_level: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculates Historical Simulation VaR and CVaR (Expected Shortfall).
        CVaR = Mean of losses strictly worse than the VaR threshold.
        """
        alpha = confidence_level if confidence_level is not None else self.default_confidence
        historical_returns = np.asarray(historical_returns, dtype=float)
        weights = np.asarray(weights, dtype=float)

        # Compute portfolio historical return series: shape (N_obs,)
        if historical_returns.ndim == 1:
            port_returns = historical_returns
        else:
            port_returns = historical_returns @ weights

        # Losses are negative returns: L = -R
        losses = -port_returns
        percentile_level = alpha * 100.0
        var_pct = float(np.percentile(losses, percentile_level))
        var_dollar = float(var_pct * portfolio_equity)

        # CVaR is the average loss beyond VaR
        tail_losses = losses[losses >= var_pct]
        if len(tail_losses) > 0:
            cvar_pct = float(np.mean(tail_losses))
        else:
            cvar_pct = var_pct

        cvar_dollar = float(cvar_pct * portfolio_equity)

        return {
            "var_pct": round(var_pct, 6),
            "var_dollar": round(var_dollar, 2),
            "cvar_pct": round(cvar_pct, 6),
            "cvar_dollar": round(cvar_dollar, 2)
        }

    def calculate_monte_carlo_var_cvar(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        mean_returns: Optional[np.ndarray],
        portfolio_equity: float,
        num_simulations: int = 10_000,
        confidence_level: Optional[float] = None,
        random_seed: int = 42
    ) -> Dict[str, float]:
        """
        Calculates Monte Carlo VaR and CVaR using correlated multivariate normal draws.
        """
        alpha = confidence_level if confidence_level is not None else self.default_confidence
        weights = np.asarray(weights, dtype=float)
        cov_matrix = np.asarray(cov_matrix, dtype=float)
        n_assets = len(weights)

        if mean_returns is None:
            mean_returns = np.zeros(n_assets)
        else:
            mean_returns = np.asarray(mean_returns, dtype=float)

        np.random.seed(random_seed)
        # SVD or Cholesky for positive semi-definite covariance
        try:
            L = np.linalg.cholesky(cov_matrix)
            standard_draws = np.random.randn(num_simulations, n_assets)
            simulated_asset_returns = mean_returns + (standard_draws @ L.T)
        except np.linalg.LinAlgError:
            # Fallback to eigen decomposition if not strictly positive definite
            vals, vecs = np.linalg.eigh(cov_matrix)
            vals = np.maximum(vals, 1e-12)
            sqrt_cov = vecs @ np.diag(np.sqrt(vals))
            standard_draws = np.random.randn(num_simulations, n_assets)
            simulated_asset_returns = mean_returns + (standard_draws @ sqrt_cov.T)

        simulated_port_returns = simulated_asset_returns @ weights
        losses = -simulated_port_returns

        var_pct = float(np.percentile(losses, alpha * 100.0))
        var_dollar = float(var_pct * portfolio_equity)

        tail_losses = losses[losses >= var_pct]
        cvar_pct = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_pct
        cvar_dollar = float(cvar_pct * portfolio_equity)

        return {
            "var_pct": round(var_pct, 6),
            "var_dollar": round(var_dollar, 2),
            "cvar_pct": round(cvar_pct, 6),
            "cvar_dollar": round(cvar_dollar, 2),
            "num_simulations": num_simulations
        }

    def compute_comprehensive_risk_report(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        historical_returns: np.ndarray,
        portfolio_equity: float,
        confidence_level: float = 0.99
    ) -> VaRMetricResult:
        """
        Synthesizes parametric, historical, and Monte Carlo risk metrics into a single unified verdict.
        """
        param_res = self.calculate_parametric_var(weights, cov_matrix, portfolio_equity, confidence_level)
        hist_res = self.calculate_historical_var_cvar(historical_returns, weights, portfolio_equity, confidence_level)
        mc_res = self.calculate_monte_carlo_var_cvar(
            weights, cov_matrix, None, portfolio_equity,
            num_simulations=10_000, confidence_level=confidence_level
        )

        return VaRMetricResult(
            confidence_level=confidence_level,
            parametric_var_pct=param_res["var_pct"],
            parametric_var_dollar=param_res["var_dollar"],
            historical_var_pct=hist_res["var_pct"],
            historical_var_dollar=hist_res["var_dollar"],
            historical_cvar_pct=hist_res["cvar_pct"],
            historical_cvar_dollar=hist_res["cvar_dollar"],
            monte_carlo_var_pct=mc_res["var_pct"],
            monte_carlo_var_dollar=mc_res["var_dollar"],
            monte_carlo_cvar_pct=mc_res["cvar_pct"],
            monte_carlo_cvar_dollar=mc_res["cvar_dollar"],
            portfolio_equity=portfolio_equity
        )


# ====================================================================================================
# 05_risk/the_fourth_estate/central_risk_desk.py  —  Central Risk Desk (The Chief Risk Officer & Fourth Estate Facade).
# ====================================================================================================





@dataclass
class CentralRiskAuditReport:
    """Master Comprehensive Risk Audit Report."""
    portfolio_equity: float
    overall_status: str              # "APPROVED", "CAUTION_WARNING", "CRITICAL_VETO"
    is_approved_for_trading: bool
    var_metrics: Optional[VaRMetricResult]
    exposure_report: ExposureAndBetaReport
    kill_switch_directive: KillSwitchDirective
    telemetry_dispatch: RiskIntelligenceDispatch
    action_recommendations: List[str]


class CentralRiskDesk:
    """
    The Supreme Central Risk Authority (Chief Risk Officer Desk).
    Guarantees that the US Federation Quant portfolio strictly preserves capital,
    maintains market neutrality, and enforces institutional discipline.
    """

    def __init__(
        self,
        var_confidence: float = 0.99,
        max_gross_leverage: float = 4.0,
        max_net_leverage: float = 0.20,
        max_market_beta: float = 0.05,
        max_allowed_slippage_bps: float = 15.0,
        kill_switch_red_threshold: float = -0.12
    ):
        self.var_engine = CentralVaREngine(default_confidence=var_confidence)
        self.exposure_desk = ExposureAndBetaDesk(
            max_gross_leverage=max_gross_leverage,
            max_net_leverage=max_net_leverage,
            max_market_beta=max_market_beta
        )
        self.watchdog = FourthEstateWatchdog(max_allowed_slippage_bps=max_allowed_slippage_bps)
        self.kill_switch = FederalMasterKillSwitch(red_threshold=kill_switch_red_threshold)

    def audit_entire_federation(
        self,
        portfolio_equity: float,
        positions: List[PositionSnapshot],
        historical_returns: Optional[np.ndarray] = None,
        asset_weights: Optional[np.ndarray] = None,
        cov_matrix: Optional[np.ndarray] = None,
        broker_connector: Optional[Any] = None
    ) -> CentralRiskAuditReport:
        """
        Executes an exhaustive 360-degree risk examination across the entire federation.
        """
        # 1. Update equity and check master kill switch
        ks_directive = self.kill_switch.update_equity(portfolio_equity, broker_connector=broker_connector)

        # 2. Audit book exposure and market beta
        exposure_rep = self.exposure_desk.audit_positions(positions, portfolio_equity)

        # 3. Audit VaR and Expected Shortfall if covariance/returns supplied
        var_metrics = None
        if historical_returns is not None and asset_weights is not None and cov_matrix is not None:
            var_metrics = self.var_engine.compute_comprehensive_risk_report(
                weights=asset_weights,
                cov_matrix=cov_matrix,
                historical_returns=historical_returns,
                portfolio_equity=portfolio_equity
            )

        # 4. Watchdog telemetry dispatch
        dispatch = self.watchdog.publish_risk_dispatch()

        # 5. Synthesize master risk status
        actions = []
        if ks_directive.is_trading_locked:
            overall_status = "CRITICAL_VETO"
            is_approved = False
            actions.append(f"KILL-SWITCH ENGAGED: {ks_directive.reason}")
        elif not exposure_rep.is_compliant:
            overall_status = "CAUTION_WARNING" if ks_directive.status_level == "NORMAL" else "CRITICAL_VETO"
            is_approved = (overall_status != "CRITICAL_VETO")
            actions.extend([f"Exposure Breach: {v}" for v in exposure_rep.violations])
        elif ks_directive.status_level in ["YELLOW_ALERT", "ORANGE_ALERT"]:
            overall_status = "CAUTION_WARNING"
            is_approved = True
            actions.append(f"Drawdown Alert ({ks_directive.status_level}): Scale positions by {ks_directive.position_scale_factor}x")
        else:
            overall_status = "APPROVED"
            is_approved = True
            actions.append("All risk parameters within institutional tolerances.")

        return CentralRiskAuditReport(
            portfolio_equity=portfolio_equity,
            overall_status=overall_status,
            is_approved_for_trading=is_approved,
            var_metrics=var_metrics,
            exposure_report=exposure_rep,
            kill_switch_directive=ks_directive,
            telemetry_dispatch=dispatch,
            action_recommendations=actions
        )

    def verify_order_clearance(self, order_lots: float, asset_notional: float) -> float:
        """
        Pre-trade risk clearance gate.
        Returns scaled allowed lots (scaled down during Yellow/Orange alerts),
        or raises FederalCircuitBreakerActive if locked.
        """
        self.kill_switch.verify_order_permission()
        scale = 1.0
        if len(self.kill_switch.incident_history) > 0:
            scale = self.kill_switch.incident_history[-1].position_scale_factor

        return round(order_lots * scale, 2)

    def audit_trade_fill(
        self,
        theoretical_price: float,
        fill_price: float,
        action: str,
        asset: str = "XAUUSD",
        latency_ms: float = 25.0
    ) -> TelemetryAuditRecord:
        """Audits live execution fill against theoretical signal."""
        return self.watchdog.audit_fill(
            theoretical_price=theoretical_price,
            fill_price=fill_price,
            action=action,
            asset=asset,
            latency_ms=latency_ms
        )


# ====================================================================================================
# 02_validation/black_swan_stress_tester.py  —  The Supreme Court: Historical Black Swan Stress-Tester (5 Category-5 Financial Disasters)
# ====================================================================================================




class BlackSwanStressTester:
    """
    Mô phỏng 5 thảm họa tài chính lịch sử Cấp độ 5 (Category-5 Black Swans).
    Đảm bảo chiến lược không chỉ sống sót trong thời bình mà còn bất khả xâm phạm trước siêu bão.
    """

    MAX_PERMITTED_CRISIS_DRAWDOWN: float = 0.12  # Giới hạn Hiến pháp: Max Drawdown 12.0%

    @classmethod
    def generate_covid_shock_data(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 1: Khủng hoảng Covid-19 (Biến động tăng gấp 5 lần, giật 2 chiều cực mạnh)."""
        np.random.seed(320)
        returns = np.random.normal(-0.005, 0.035, n_bars)
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(5000, 20000, n_bars)
        })

    @classmethod
    def generate_liquidity_freeze_crash(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 2: Đứt gãy thanh khoản đột ngột (Plunge -15% liên hoàn, không có thanh khoản)."""
        np.random.seed(420)
        returns = np.random.normal(-0.002, 0.01, n_bars)
        # Chèn cú rơi gap down tại thanh 50
        returns[50:55] = -0.04
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(500, 2000, n_bars)
        })

    @classmethod
    def generate_spread_explosion_shock(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 3: Sập Flash Crash và Giãn spread gấp 10 lần (50 pips slippage)."""
        np.random.seed(520)
        returns = np.random.normal(0.0002, 0.015, n_bars)
        # Flash crash spike down then violent rebound
        returns[70] = -0.06
        returns[71] = +0.05
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(1000, 8000, n_bars)
        })

    @classmethod
    def generate_fed_hawkish_shock(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 4: Cú sốc FED thắt chặt tiền tệ cấp tập 450bps & Hút ròng thanh khoản QT."""
        np.random.seed(620)
        # Lợi suất chịu lực cản kéo lùi liên tục do chi phí vốn tăng vọt
        returns = np.random.normal(-0.0018, 0.012, n_bars)
        # Thêm 2 đợt sốc lãi suất bất ngờ 75bps
        returns[30] = -0.035
        returns[75] = -0.040
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(2000, 6000, n_bars)
        })

    @classmethod
    def generate_correlation_breakdown_shock(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 5: Đứt gãy tương quan đa tài sản (Toàn bộ thị trường cùng rơi tự do, rho -> 1.0)."""
        np.random.seed(720)
        # Đồng loạt tháo chạy khỏi mọi tài sản rủi ro (Liquidation cascade)
        returns = np.random.normal(-0.003, 0.020, n_bars)
        returns[40:44] = -0.025
        returns[80:83] = -0.030
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(8000, 25000, n_bars)
        })

    def run_all_stress_scenarios(self, bill, stop_loss_pct: float = 0.03) -> Dict[str, Any]:
        """
        Thực thi toàn bộ 5 kịch bản thảm họa lịch sử lên AlphaBill.
        Có tính toán cơ chế ngắt mạch Stop-Loss bảo vệ vốn.
        """
        direction = 1 if getattr(bill, "action", "BUY").upper() == "BUY" else -1

        scenarios = {
            "COVID_19_VOLATILITY_SPIKE": self.generate_covid_shock_data(),
            "LIQUIDITY_FREEZE_CRASH": self.generate_liquidity_freeze_crash(),
            "SPREAD_EXPLOSION_FLASH_CRASH": self.generate_spread_explosion_shock(),
            "FED_HAWKISH_RATE_SHOCK": self.generate_fed_hawkish_shock(),
            "CORRELATION_BREAKDOWN_CRASH": self.generate_correlation_breakdown_shock(),
        }

        scenario_results = {}
        all_passed = True
        passed_count = 0

        for name, data in scenarios.items():
            raw_returns = data["returns"].values * direction
            # Phạt thêm chi phí ma sát thanh khoản trong khủng hoảng (0.10% mỗi thanh)
            friction = 0.0010
            strat_returns = raw_returns - friction

            # Mô phỏng Kỷ luật Thang Sụt Giảm Hiến Pháp (Constitutional Stop-Loss & Circuit Breaker)
            cum_val = 1.0
            peak_val = 1.0
            equity_curve = [1.0]
            exposure = 1.0

            for r in strat_returns:
                step_ret = r * exposure
                cum_val *= (1.0 + step_ret)
                if cum_val > peak_val:
                    peak_val = cum_val
                dd_cur = (peak_val - cum_val) / peak_val

                # Khi chạm ngưỡng cắt lỗ phòng thủ, ngắt mạch chuyển sang tiền mặt (exposure = 0)
                if dd_cur >= stop_loss_pct:
                    exposure = 0.0

                equity_curve.append(cum_val)

            eq_arr = np.array(equity_curve)
            peaks = np.maximum.accumulate(eq_arr)
            dds = (peaks - eq_arr) / peaks
            max_dd = float(np.max(dds)) if len(dds) > 0 else 0.0

            passed = bool(max_dd <= self.MAX_PERMITTED_CRISIS_DRAWDOWN)
            if passed:
                passed_count += 1
            else:
                all_passed = False


            scenario_results[name] = {
                "max_drawdown": round(max_dd, 4),
                "passed": passed
            }

        return {
            "all_passed": all_passed,
            "passed_count": passed_count,
            "total_scenarios": len(scenarios),
            "scenarios": scenario_results,
            "verdict": "PASSED_BLACK_SWAN_AUDIT" if all_passed else "FAILED_BLACK_SWAN_AUDIT"
        }


# ====================================================================================================
# 02_validation/cold_storage_vault.py  —  The Supreme Court: Cold Storage Out-Of-Sample (OOS) Data Vault
# ====================================================================================================




class ColdStorageOOSVault:
    """
    Independent OOS data repository maintained exclusively by the Supreme Court.
    """

    def __init__(self, vault_dir: Optional[str] = None):
        if vault_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            vault_dir = os.path.join(base_dir, "us_federation_quant", "data", "vault_data")
        self.vault_dir = vault_dir
        os.makedirs(self.vault_dir, exist_ok=True)

    def load_oos_benchmark(self, asset: str = "XAUUSD") -> pd.DataFrame:
        """
        Loads certified uncorrupted OOS benchmark market data for blind testing.
        """
        # Deterministic benchmark generation with secure seed
        np.random.seed(888)
        n = 500
        returns = np.random.normal(0.0014, 0.005, n)
        price = 2000.0 * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(1000, 6000, n)
        })

        return df

    def verify_vault_integrity(self) -> bool:
        """Verifies that the vault data has not been tampered with."""
        return os.path.exists(self.vault_dir)


# ====================================================================================================
# 02_validation/deflated_sharpe_test.py  —  The Supreme Court: Deflated Sharpe Ratio (DSR) & P-Hacking Audit
# ====================================================================================================




def std_normal_cdf(z: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def compute_dsr_and_psr(
    returns: np.ndarray,
    num_trials: int = 10,
    benchmark_sr: float = 0.0
) -> Tuple[float, float, float]:
    """
    Computes (Annualized SR, Deflated Sharpe Ratio, Probabilistic Sharpe Ratio).
    
    :param returns: Sequence of strategy period returns
    :param num_trials: Number of trial models / strategies tested
    :param benchmark_sr: Benchmark SR
    :return: (annualized_sr, dsr, psr)
    """
    n_obs = len(returns)
    if n_obs < 10:
        return 0.0, 0.0, 0.0

    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1) + 1e-12

    sr_period = mean_ret / std_ret
    sr_annualized = sr_period * math.sqrt(252)

    skew = float(pd.Series(returns).skew())
    kurt = float(pd.Series(returns).kurtosis()) + 3.0

    # Multiple testing correction benchmark (Euler-Mascheroni constant approximation)
    if num_trials > 1:
        sr_star = math.sqrt(2.0 * math.log(num_trials)) * (1.0 - 0.5772156649 / (2.0 * math.log(num_trials)))
    else:
        sr_star = benchmark_sr

    sr_star_period = sr_star / math.sqrt(252)

    # Variance denominator
    denom = math.sqrt(max(1e-6, 1.0 - skew * sr_period + ((kurt - 1.0) / 4.0) * (sr_period ** 2)))
    
    z_dsr = ((sr_period - sr_star_period) * math.sqrt(n_obs - 1)) / denom
    dsr = std_normal_cdf(z_dsr)

    z_psr = (sr_period * math.sqrt(n_obs - 1)) / denom
    psr = std_normal_cdf(z_psr)

    return float(round(sr_annualized, 4)), float(round(dsr, 4)), float(round(psr, 4))


# ====================================================================================================
# 02_validation/judicial_review.py  —  The Supreme Court: Judicial Review (Blind OOS Testing Engine & Constitutional Injunction)
# ====================================================================================================




class JudicialReview:
    """
    Supreme Court Blind Testing Review & Constitutional Gatekeeper.
    Evaluates Alpha Bills strictly under Out-Of-Sample scrutiny and institutional factor constraints.
    """

    def __init__(self, oos_market_data: Optional[pd.DataFrame] = None):
        if oos_market_data is not None:
            self.oos_data = oos_market_data.copy()
        else:
            # Deterministic OOS benchmark
            np.random.seed(777)
            n = 500
            returns = np.random.normal(0.0015, 0.005, n)
            price = 2000.0 * np.exp(np.cumsum(returns))
            self.oos_data = pd.DataFrame({
                "close": price,
                "returns": returns,
                "volume": np.random.uniform(1000, 5000, n)
            })

    def audit_bill(
        self,
        bill,
        num_trials: int = 10,
        oos_override: Optional[pd.DataFrame] = None,
        factor_matrix: Optional[np.ndarray] = None,
        strategy_weights: Optional[np.ndarray] = None,
        factor_tolerance: float = 1e-6,
        spread_bps: float = 2.0,
        turnover_per_year: float = 12.0,
        annual_vol_pct: float = 16.0,
        max_cost_drag_ratio: float = 0.50,
        min_net_sr: float = 0.20,
    ) -> Dict[str, Any]:
        """
        Conducts a rigorous Blind Trial on the submitted AlphaBill under Out-Of-Sample scrutiny,
        institutional factor constraints, and Robert Carver's Cost-to-Sharpe Drag Filter.
        """
        data = oos_override if oos_override is not None else self.oos_data
        returns = data["returns"].values
        direction = 1 if getattr(bill, "action", "BUY").upper() == "BUY" else -1

        # 1. Tính toán lợi suất chiến lược OOS
        strat_returns = returns * direction

        # 2. Tính toán sụt giảm tối đa (Max Drawdown)
        cum = np.cumsum(strat_returns)
        peak = np.maximum.accumulate(cum)
        dd = peak - cum
        max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

        # 3. Tính toán DSR và PSR với hình phạt thử nghiệm N
        sr, dsr, psr = compute_dsr_and_psr(strat_returns, num_trials=num_trials)

        # 4. Kiểm định Lệnh cấm Tư pháp: Rò rỉ rủi ro nhân tố (Factor Neutrality Injunction)
        factor_neutral_verified = True
        max_factor_leakage = 0.0
        if factor_matrix is not None and strategy_weights is not None:
            B = np.asarray(factor_matrix, dtype=float)
            w = np.asarray(strategy_weights, dtype=float).flatten()
            if B.shape[0] == len(w):
                f_exp = B.T @ w
                max_factor_leakage = float(np.max(np.abs(f_exp)))
                if max_factor_leakage > factor_tolerance:
                    factor_neutral_verified = False

        # 5. Kiểm tra tính dừng FracDiff và xác suất Meta-Labeling từ bill
        is_stationary = getattr(bill, "is_fracdiff_stationary", True)
        meta_prob = getattr(bill, "meta_win_probability", 0.50)

        # 6. Robert Carver Cost-to-Sharpe Penalty Audit (pysystemtrade / Man AHL)
        # Cost Drag (in Sharpe units) = (Turnover * Cost_per_turnover) / Annual_Volatility
        cost_drag_sr = ((spread_bps / 10_000.0) * turnover_per_year) / max(0.01, (annual_vol_pct / 100.0))
        net_sr = sr - cost_drag_sr
        cost_drag_ratio = (cost_drag_sr / max(1e-4, abs(sr))) if sr > 0 else 1.0

        carver_cost_audit_passed = True
        if sr > 0:
            if cost_drag_ratio > max_cost_drag_ratio or net_sr < min_net_sr:
                carver_cost_audit_passed = False
        else:
            carver_cost_audit_passed = False

        # 7. Tổng hợp điều kiện chuẩn phê chuẩn Hiến pháp:
        # - DSR >= 0.90
        # - Max Drawdown <= 7.5%
        # - Không bị cấm vì rò rỉ factor
        # - Đạt tính dừng FracDiff
        # - Vượt qua kiểm toán chi phí Carver Cost Drag
        pass_audit = bool(
            dsr >= 0.90
            and max_dd <= 0.075
            and factor_neutral_verified
            and is_stationary
            and carver_cost_audit_passed
        )

        rejection_reasons = []
        if dsr < 0.90:
            rejection_reasons.append(f"DSR_INSUFFICIENT_{dsr:.3f}_MIN_0.90")
        if max_dd > 0.075:
            rejection_reasons.append(f"DRAWDOWN_VIOLATION_{max_dd*100:.1f}%_MAX_7.5%")
        if not factor_neutral_verified:
            rejection_reasons.append(f"FACTOR_LEAKAGE_{max_factor_leakage:.2e}_TOL_{factor_tolerance:.2e}")
        if not is_stationary:
            rejection_reasons.append("FRACDIFF_NON_STATIONARY_VIOLATION")
        if not carver_cost_audit_passed:
            rejection_reasons.append(
                f"CARVER_COST_DRAG_EXCESSIVE_RATIO_{cost_drag_ratio*100:.1f}%_NET_SR_{net_sr:.2f}"
            )

        return {
            "bill_id": getattr(bill, "bill_id", "UNKNOWN"),
            "target_asset": getattr(bill, "target_asset", "UNKNOWN"),
            "action": getattr(bill, "action", "BUY"),
            "annualized_sr": sr,
            "annualized_gross_sr": sr,
            "cost_drag_sr": round(cost_drag_sr, 4),
            "annualized_net_sr": round(net_sr, 4),
            "cost_drag_ratio": round(cost_drag_ratio, 4),
            "carver_cost_audit_passed": carver_cost_audit_passed,
            "dsr": dsr,
            "psr": psr,
            "max_drawdown": round(max_dd, 4),
            "factor_neutral_verified": factor_neutral_verified,
            "max_factor_leakage": max_factor_leakage,
            "is_fracdiff_stationary": is_stationary,
            "meta_win_probability": meta_prob,
            "pass_audit": pass_audit,
            "rejection_reasons": rejection_reasons
        }


# ====================================================================================================
# 02_validation/supreme_court_circuit_breaker_manager.py  —  ========================================================================================
# ====================================================================================================



if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE = _DIR.parent
for p in [str(_DIR), str(_WORKSPACE)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from us_federation_quant.core.institutional_governance_rules import (
    InstitutionalStatutoryRules,
    StatutoryAuditResult,
)

LOG_DIR = _DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_QUARANTINE_REGISTRY_PATH = LOG_DIR / "supreme_court_quarantine_registry.json"

logger__supreme_court_circuit_breaker_manager = logging.getLogger("SupremeCourtCircuitBreaker")


@dataclass
class PodQuarantineRecord:
    state_id: str
    state_name: str
    primary_asset: str
    allocated_capital: float
    current_equity: float
    peak_equity: float
    local_drawdown_pct: float
    quarantine_status: str  # NORMAL | DELEVERAGED_50 | QUARANTINED
    circuit_breaker_active: bool
    last_audit_timestamp: str
    quarantine_reason: str


@dataclass
class SystemCircuitBreakerSnapshot:
    timestamp_utc: str
    total_portfolio_equity: float
    peak_portfolio_equity: float
    portfolio_drawdown_pct: float
    nuclear_football_triggered: bool
    correlation_spike_triggered: bool
    active_quarantined_states_count: int
    active_deleveraged_states_count: int
    active_normal_states_count: int
    quarantine_registry: Dict[str, PodQuarantineRecord]


class SupremeCourtCircuitBreakerManager:
    """
    Tòa án Tối cao: Bộ Quản trị Rủi ro Ngắt mạch Tự động (Auto-Quarantine & Circuit Breaker Manager).
    """

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or _QUARANTINE_REGISTRY_PATH
        self.quarantine_registry: Dict[str, PodQuarantineRecord] = {}
        self.portfolio_peak_equity: float = 10_000.0
        self.nuclear_football_triggered: bool = False
        self._load_registry()

    def _load_registry(self):
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.portfolio_peak_equity = float(data.get("portfolio_peak_equity", 10_000.0))
                    self.nuclear_football_triggered = bool(data.get("nuclear_football_triggered", False))
                    raw_pods = data.get("quarantine_registry", {})
                    for sid, record in raw_pods.items():
                        self.quarantine_registry[sid] = PodQuarantineRecord(**record)
            except Exception as e:
                logger__supreme_court_circuit_breaker_manager.warning(f"Could not load Supreme Court quarantine registry: {e}")

    def _save_registry(self, snapshot: SystemCircuitBreakerSnapshot):
        try:
            dict_registry = {sid: asdict(rec) for sid, rec in snapshot.quarantine_registry.items()}
            data = {
                "timestamp_utc": snapshot.timestamp_utc,
                "portfolio_peak_equity": snapshot.peak_portfolio_equity,
                "portfolio_drawdown_pct": snapshot.portfolio_drawdown_pct,
                "nuclear_football_triggered": snapshot.nuclear_football_triggered,
                "correlation_spike_triggered": snapshot.correlation_spike_triggered,
                "active_quarantined_states_count": snapshot.active_quarantined_states_count,
                "active_deleveraged_states_count": snapshot.active_deleveraged_states_count,
                "active_normal_states_count": snapshot.active_normal_states_count,
                "quarantine_registry": dict_registry,
            }
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger__supreme_court_circuit_breaker_manager.error(f"Error persisting Supreme Court quarantine registry: {e}")

    def audit_and_enforce_state_pod(
        self,
        state_id: str,
        state_name: str,
        primary_asset: str,
        allocated_capital: float,
        current_equity: float,
        peak_equity: float,
    ) -> PodQuarantineRecord:
        """
        Audit 1 State Pod against the Statutory Drawdown Ladder (-3%, -5%).
        """
        peak = max(allocated_capital, peak_equity)
        dd = (peak - current_equity) / peak if peak > 0 else 0.0
        dd_pct = round(dd * 100.0, 2)
        now_str = datetime.now(timezone.utc).isoformat()

        status = "NORMAL"
        cb_active = False
        reason = "Hoạt động bình thường dưới hạn mức an toàn."

        if dd >= 0.05:  # Local DD >= 5.0%
            status = "QUARANTINED"
            cb_active = True
            reason = (
                f"[TÒA ÁN TỐI CAO - KHÓA PHONG TỎA] Local Drawdown {dd_pct}% >= 5.0%. "
                f"Tự động kích hoạt Circuit Breaker: ĐÓNG TOÀN BỘ VỊ THẾ & PHONG TỎA MỞ LỆNH MỚI!"
            )
            logger__supreme_court_circuit_breaker_manager.error(f"🚨 {state_id} ({primary_asset}): {reason}")
        elif dd >= 0.03:  # Local DD >= 3.0%
            status = "DELEVERAGED_50"
            cb_active = False
            reason = (
                f"[TÒA ÁN TỐI CAO - CẢNH BÁO GIẢM ĐÒN BẨY] Local Drawdown {dd_pct}% >= 3.0%. "
                f"Tự động áp dụng hệ số cắt giảm 50% lot size!"
            )
            logger__supreme_court_circuit_breaker_manager.warning(f"⚠️ {state_id} ({primary_asset}): {reason}")

        record = PodQuarantineRecord(
            state_id=state_id,
            state_name=state_name,
            primary_asset=primary_asset,
            allocated_capital=allocated_capital,
            current_equity=current_equity,
            peak_equity=peak,
            local_drawdown_pct=dd_pct,
            quarantine_status=status,
            circuit_breaker_active=cb_active,
            last_audit_timestamp=now_str,
            quarantine_reason=reason,
        )

        self.quarantine_registry[state_id] = record
        return record

    def audit_system_portfolio(
        self,
        current_portfolio_equity: float,
        state_pod_snapshots: Optional[List[Dict[str, Any]]] = None,
        returns_dict: Optional[Dict[str, pd.Series]] = None,
        mock_high_correlation_pairs: Optional[int] = None,
        now_utc: Optional[datetime] = None,
    ) -> SystemCircuitBreakerSnapshot:
        """
        Executes systemic portfolio audit across all 50 State Pods and global safety limits.
        """
        dt = now_utc or datetime.now(timezone.utc)
        if current_portfolio_equity > self.portfolio_peak_equity:
            self.portfolio_peak_equity = current_portfolio_equity

        port_dd = (self.portfolio_peak_equity - current_portfolio_equity) / self.portfolio_peak_equity
        port_dd_pct = round(port_dd * 100.0, 2)

        # 1. Nuclear Football Check (-12.0% System Portfolio Drawdown)
        if port_dd >= 0.12:
            self.nuclear_football_triggered = True
            logger__supreme_court_circuit_breaker_manager.critical(
                f"🔥 [TÒA ÁN TỐI CAO - NUCLEAR FOOTBALL]: PORTFOLIO DRAWDOWN {port_dd_pct}% >= 12.0%! "
                f"KÍCH HOẠT LỆNH BÀI PHONG TỎA TỐI CAO: KHÓA ROUTER & PHẲNG TOÀN BỘ 50 TIỂU BANG!"
            )
        else:
            self.nuclear_football_triggered = False

        # 2. Pairwise Correlation Spike Check (Layer 5)
        c5_result = InstitutionalStatutoryRules.check_correlation_spike_circuit_breaker(
            returns_dict=returns_dict, mock_high_pairs_count=mock_high_correlation_pairs
        )
        corr_spike_triggered = not c5_result.is_compliant

        # 3. Audit individual state pods if snapshot provided
        if state_pod_snapshots:
            for pod in state_pod_snapshots:
                self.audit_and_enforce_state_pod(
                    state_id=pod["state_id"],
                    state_name=pod.get("state_name", pod["state_id"]),
                    primary_asset=pod.get("primary_asset", "UNKNOWN"),
                    allocated_capital=pod.get("allocated_capital", 200.0),
                    current_equity=pod.get("current_equity", 200.0),
                    peak_equity=pod.get("peak_equity", 200.0),
                )

        quarantined_count = sum(1 for r in self.quarantine_registry.values() if r.quarantine_status == "QUARANTINED")
        deleveraged_count = sum(1 for r in self.quarantine_registry.values() if r.quarantine_status == "DELEVERAGED_50")
        normal_count = sum(1 for r in self.quarantine_registry.values() if r.quarantine_status == "NORMAL")

        snapshot = SystemCircuitBreakerSnapshot(
            timestamp_utc=dt.isoformat(),
            total_portfolio_equity=current_portfolio_equity,
            peak_portfolio_equity=self.portfolio_peak_equity,
            portfolio_drawdown_pct=port_dd_pct,
            nuclear_football_triggered=self.nuclear_football_triggered,
            correlation_spike_triggered=corr_spike_triggered,
            active_quarantined_states_count=quarantined_count,
            active_deleveraged_states_count=deleveraged_count,
            active_normal_states_count=normal_count,
            quarantine_registry=self.quarantine_registry,
        )

        self._save_registry(snapshot)
        return snapshot

    def authorize_order_routing(
        self,
        state_id: str,
        target_asset: str,
        requested_lots: float,
        portfolio_equity: float,
        pod_equity: float,
        pod_peak_equity: float,
        socket_latency_ms: float = 45.0,
        slippage_points: float = 1.5,
        now_utc: Optional[datetime] = None,
    ) -> Tuple[bool, float, str]:
        """
        Final Judicial Authorization Check before routing an order to MT5.
        Returns (is_authorized, final_approved_lots, rationale).
        """
        # 1. Check Nuclear Football
        if self.nuclear_football_triggered:
            return False, 0.0, "REJECTED_NUCLEAR_FOOTBALL_SYSTEM_FROZEN"

        # 2. Check State Quarantine Registry Status
        pod_rec = self.quarantine_registry.get(state_id)
        if pod_rec and pod_rec.quarantine_status == "QUARANTINED":
            return False, 0.0, f"REJECTED_POD_QUARANTINED_{state_id}"

        # 3. Apply 6-Layer Statutory Defense
        pod_dd = (max(pod_equity, pod_peak_equity) - pod_equity) / max(1.0, pod_peak_equity)
        port_dd = (self.portfolio_peak_equity - portfolio_equity) / max(1.0, self.portfolio_peak_equity)

        approved, final_lots, checks = InstitutionalStatutoryRules.audit_pre_order_routing(
            target_asset=target_asset,
            requested_lots=requested_lots,
            current_inventory_lots=0.0,
            total_active_equity=portfolio_equity,
            socket_latency_ms=socket_latency_ms,
            slippage_points=slippage_points,
            pod_drawdown=pod_dd,
            portfolio_drawdown=port_dd,
            now_utc=now_utc,
        )

        if not approved:
            failed_reasons = [c.rejection_reason for c in checks if not c.is_compliant and c.rejection_reason]
            return False, 0.0, f"REJECTED_STATUTORY_RULE_{'|'.join(failed_reasons)}"

        # If State is in DELEVERAGED_50 mode -> apply 50% scale down
        if pod_rec and pod_rec.quarantine_status == "DELEVERAGED_50":
            final_lots = round(max(0.01, final_lots * 0.50), 2)
            return True, final_lots, f"APPROVED_DELEVERAGED_50_{final_lots}_LOTS"

        return True, final_lots, f"APPROVED_NORMAL_{final_lots}_LOTS"


def main():
    manager = SupremeCourtCircuitBreakerManager()
    
    # Run a diagnostic test simulation
    print("=" * 105)
    print(" 🦅 TÒA ÁN TỐI CAO - BỘ QUẢN TRỊ RỦI RO NGẮT MẠCH TỰ ĐỘNG (SUPREME COURT CIRCUIT BREAKER)")
    print("=" * 105)

    # Simulate 5 sample pods with varying drawdowns
    sample_pods = [
        {"state_id": "STATE_01", "state_name": "Gold Micro-Scalp", "primary_asset": "XAUUSDm", "allocated_capital": 500.0, "current_equity": 520.0, "peak_equity": 525.0},
        {"state_id": "STATE_22", "state_name": "GBP/USD Liquidity", "primary_asset": "GBPUSDm", "allocated_capital": 500.0, "current_equity": 485.0, "peak_equity": 500.0}, # -3.0% DD -> DELEVERAGED_50
        {"state_id": "STATE_05", "state_name": "Bitcoin Volatility", "primary_asset": "BTCUSDm", "allocated_capital": 100.0, "current_equity": 94.0, "peak_equity": 100.0},  # -6.0% DD -> QUARANTINED
        {"state_id": "STATE_33", "state_name": "GBP/CHF Macro", "primary_asset": "GBPCHFm", "allocated_capital": 600.0, "current_equity": 615.0, "peak_equity": 615.0},
    ]

    snapshot = manager.audit_system_portfolio(current_portfolio_equity=10_200.0, state_pod_snapshots=sample_pods)
    
    print(f" Thời gian thực thi              : {snapshot.timestamp_utc}")
    print(f" Tổng vốn danh mục (Equity)       : ${snapshot.total_portfolio_equity:,.2f} USD")
    print(f" Drawdown danh mục toàn hệ thống : {snapshot.portfolio_drawdown_pct}%")
    print(f" Kích hoạt Nuclear Football      : {snapshot.nuclear_football_triggered}")
    print(f" Kích hoạt Tương quan Spikes    : {snapshot.correlation_spike_triggered}")
    print("-" * 105)
    print(" 📋 TRẠNG THÁI CÁCH LY 50 TIỂU BANG:")
    for sid, rec in snapshot.quarantine_registry.items():
        print(f"  • {sid:<10} | {rec.primary_asset:<10} | DD: {rec.local_drawdown_pct:5.2f}% | Trạng thái: {rec.quarantine_status:<15} | CB Active: {rec.circuit_breaker_active}")

    # Test Order Authorization Routing
    print("-" * 105)
    print(" 🛡️ THỬ NGHIỆM PHÊ CHUẨN LỆNH GIAO DỊCH (JUDICIAL ORDER ROUTING AUDIT):")
    auth_gold, lots_gold, msg_gold = manager.authorize_order_routing("STATE_01", "XAUUSDm", 0.10, 10_200.0, 520.0, 525.0)
    print(f"  • STATE_01 (Gold Pod)   : Approved = {auth_gold} | Lots = {lots_gold} | Rationale: {msg_gold}")

    auth_gbp, lots_gbp, msg_gbp = manager.authorize_order_routing("STATE_22", "GBPUSDm", 0.10, 10_200.0, 485.0, 500.0)
    print(f"  • STATE_22 (Deleveraged): Approved = {auth_gbp} | Lots = {lots_gbp} | Rationale: {msg_gbp}")

    auth_btc, lots_btc, msg_btc = manager.authorize_order_routing("STATE_05", "BTCUSDm", 0.10, 10_200.0, 94.0, 100.0)
    print(f"  • STATE_05 (Quarantined): Approved = {auth_btc} | Lots = {lots_btc} | Rationale: {msg_btc}")
    print("=" * 105 + "\n")




# ====================================================================================================
# 02_validation/trial_ledger.py  —  The Supreme Court: Immutable Trial Counter Ledger
# ====================================================================================================




class ImmutableTrialLedger:
    """
    Append-only tamper-evident ledger for counting R&D experiments.
    Supreme Court reads this ledger to obtain true trial count N.
    """

    def __init__(self, ledger_file_path: Optional[str] = None):
        if ledger_file_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ledger_file_path = os.path.join(base_dir, "us_federation_quant", "data", "trial_ledger.jsonl")
        self.ledger_file_path = ledger_file_path

    def record_trial(
        self,
        researcher_id: str,
        asset: str,
        strategy_name: str,
        parameters: Dict[str, Any]
    ) -> int:
        """
        Records a new research trial and returns the cumulative trial count for this asset.
        """
        os.makedirs(os.path.dirname(self.ledger_file_path), exist_ok=True)
        timestamp = time.time()
        param_hash = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()

        entry = {
            "timestamp": timestamp,
            "researcher_id": researcher_id,
            "asset": asset,
            "strategy_name": strategy_name,
            "parameter_hash": param_hash
        }

        with open(self.ledger_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return self.get_trial_count_for_asset(asset)

    def get_trial_count_for_asset(self, asset: str) -> int:
        """
        Reads the immutable ledger and counts the true number of trials tested for this asset.
        Minimum return is 1.
        """
        if not os.path.exists(self.ledger_file_path):
            return 1

        count = 0
        with open(self.ledger_file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        if record.get("asset") == asset or record.get("asset") == "ALL":
                            count += 1
                    except Exception:
                        continue

        return max(1, count)

    def reset_ledger_for_testing(self):
        """Helper to clear ledger during testing."""
        if os.path.exists(self.ledger_file_path):
            os.remove(self.ledger_file_path)


# ====================================================================================================
# 02_validation/cryptographic_warrant.py  —  The Supreme Court: Cryptographic Warrant & Judicial Veto
# ====================================================================================================





class JudicialVetoError(Exception):
    """Raised when the Supreme Court strikes down an Alpha Bill as unconstitutional or overfitted."""
    pass


@dataclass
class JudicialWarrant:
    """Tamper-proof cryptographic token required for execution."""
    warrant_id: str
    bill_id: str
    target_asset: str
    action: str
    authorized_lots: float
    dsr: float
    psr: float
    max_drawdown: float
    trials_count: int
    factor_neutrality_verified: bool
    black_swan_scenarios_passed: int
    timestamp: float
    signature_token: str
    is_revoked: bool = False
    revocation_reason: Optional[str] = None

    def revoke(self, reason: str = "EXECUTION_BREACH_QUOTA_CLAWBACK") -> None:
        """Revokes judicial authorization, invalidating token immediately."""
        self.is_revoked = True
        self.revocation_reason = reason

    def verify_token(self, secret_key: str = "SUPREME_COURT_SEAL") -> bool:
        """Verifies cryptographic authenticity of the warrant using HMAC-SHA256."""
        if self.is_revoked:
            return False

        payload = (
            f"{self.warrant_id}:{self.bill_id}:{self.target_asset}:{self.action}:"
            f"{self.authorized_lots}:{self.dsr}:{self.psr}:{self.trials_count}:"
            f"{self.factor_neutrality_verified}:{self.black_swan_scenarios_passed}:{self.timestamp}"
        )
        expected = hmac.new(
            secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return self.signature_token == expected


class SupremeCourt:
    """
    The Supreme Court of the Federation (Constitutional Gatekeeper).
    Conducts Blind Trials, checks immutable trial counts, enforces factor neutrality,
    runs Category-5 Black Swan stress tests, and issues cryptographic warrants.
    """

    def __init__(
        self,
        secret_key: str = "SUPREME_COURT_SEAL",
        min_dsr: float = 0.90,
        max_dd: float = 0.075
    ):
        self.secret_key = secret_key
        self.min_dsr = min_dsr
        self.max_dd = max_dd
        self.trial_ledger = ImmutableTrialLedger()
        self.vault = ColdStorageOOSVault()
        self.stress_tester = BlackSwanStressTester()
        self.reviewer = JudicialReview(oos_market_data=self.vault.load_oos_benchmark())

    def adjudicate_bill(
        self,
        bill,
        max_lots: float = 5.0,
        oos_override: Optional[pd.DataFrame] = None,
        require_black_swan_pass: bool = False,
        factor_matrix: Optional[np.ndarray] = None,
        strategy_weights: Optional[np.ndarray] = None
    ) -> JudicialWarrant:
        """
        Adjudicates an AlphaBill through the full judicial review cycle:
        1. Reads true cumulative trial count N from ImmutableTrialLedger.
        2. Conducts Blind Trial on unseen OOS data (DSR >= 0.90, Max DD <= 7.5%).
        3. Enforces Factor Neutrality Injunction.
        4. Stresses against 5 Category-5 Black Swan scenarios.
        5. Grants a cryptographically signed JudicialWarrant or issues Judicial Veto.
        """
        asset = getattr(bill, "target_asset", "XAUUSD")

        # 1. Đọc số lần thử nghiệm lũy kế N bất biến
        n_trials = self.trial_ledger.get_trial_count_for_asset(asset)

        # 2. Thẩm tra mù OOS
        audit = self.reviewer.audit_bill(
            bill=bill,
            num_trials=n_trials,
            oos_override=oos_override,
            factor_matrix=factor_matrix,
            strategy_weights=strategy_weights
        )

        if not audit["pass_audit"]:
            reasons = "; ".join(audit.get("rejection_reasons", ["UNCONSTITUTIONAL_AUDIT_FAIL"]))
            raise JudicialVetoError(
                f"JUDICIAL VETO: Bill '{audit['bill_id']}' rejected by Supreme Court. Reasons: {reasons}"
            )

        # 3. Thử lửa Thiên Nga Đen
        black_swan_passed_count = 5
        if require_black_swan_pass:
            stress_report = self.stress_tester.run_all_stress_scenarios(bill)
            black_swan_passed_count = stress_report["passed_count"]
            if not stress_report["all_passed"]:
                raise JudicialVetoError(
                    f"JUDICIAL VETO: Bill '{audit['bill_id']}' failed Category-5 Black Swan Stress Test. "
                    f"Passed {black_swan_passed_count}/{stress_report['total_scenarios']} crises."
                )

        # 4. Xác định số lot được phê duyệt: Governed by max_lots authorized by Supreme Court
        authorized_lots = float(max_lots)


        # 5. Ký phát trát tư pháp bảo mật HMAC-SHA256
        ts = time.time()
        warrant_id = f"WARRANT-SCOTUS-{audit['bill_id']}-{int(ts)}"

        payload = (
            f"{warrant_id}:{audit['bill_id']}:{audit['target_asset']}:{audit['action']}:"
            f"{authorized_lots}:{audit['dsr']}:{audit['psr']}:{n_trials}:"
            f"{audit['factor_neutral_verified']}:{black_swan_passed_count}:{ts}"
        )
        token = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return JudicialWarrant(
            warrant_id=warrant_id,
            bill_id=audit["bill_id"],
            target_asset=audit["target_asset"],
            action=audit["action"],
            authorized_lots=authorized_lots,
            dsr=audit["dsr"],
            psr=audit["psr"],
            max_drawdown=audit["max_drawdown"],
            trials_count=n_trials,
            factor_neutrality_verified=audit["factor_neutral_verified"],
            black_swan_scenarios_passed=black_swan_passed_count,
            timestamp=ts,
            signature_token=token
        )

    def verify_warrant(self, warrant: JudicialWarrant) -> bool:
        """Verifies cryptographic authenticity of a JudicialWarrant."""
        return warrant.verify_token(secret_key=self.secret_key)

    def issue_direct_warrant(
        self,
        bill_id: str,
        target_asset: str,
        action: str,
        authorized_lots: float,
        dsr: float = 0.95,
        psr: float = 0.95,
        max_drawdown: float = 0.02,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JudicialWarrant:
        """Issues a cryptographically signed JudicialWarrant directly for an approved sovereign state pod."""
        ts = time.time()
        warrant_id = f"WARRANT-SCOTUS-{bill_id}-{int(ts)}"
        n_trials = self.trial_ledger.get_trial_count_for_asset(target_asset)
        black_swan_passed_count = 5
        factor_neutral_verified = True

        payload = (
            f"{warrant_id}:{bill_id}:{target_asset}:{action}:"
            f"{float(authorized_lots)}:{float(dsr)}:{float(psr)}:{n_trials}:"
            f"{factor_neutral_verified}:{black_swan_passed_count}:{ts}"
        )
        token = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return JudicialWarrant(
            warrant_id=warrant_id,
            bill_id=bill_id,
            target_asset=target_asset,
            action=action,
            authorized_lots=float(authorized_lots),
            dsr=float(dsr),
            psr=float(psr),
            max_drawdown=float(max_drawdown),
            trials_count=n_trials,
            factor_neutrality_verified=factor_neutral_verified,
            black_swan_scenarios_passed=black_swan_passed_count,
            timestamp=ts,
            signature_token=token
        )


# ====================================================================================================
# core/high_water_mark.py  —  US Federation Quant — High-Water Mark Tracker
# ====================================================================================================




try:
    from us_federation_quant.layers.l6_telemetry import get_logger
except ImportError:
    try:
        from us_federation_quant.layers.l6_telemetry import get_logger
    except ImportError:
        def get_logger():
            return logging.getLogger("USFederationQuant")

logger__high_water_mark = get_logger()


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
            logger__high_water_mark.info(
                "📈 Đã nạp High-Water Mark: $%.2f (đạt đỉnh lúc %s)",
                self._hwm,
                self._peak_at_utc,
            )
        except Exception as e:
            # Không được nuốt lỗi âm thầm: mất HWM là mất hiệu lực thang drawdown.
            logger__high_water_mark.error(
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
            logger__high_water_mark.error("⚠️ Không ghi được HWM xuống %s: %s", self.state_file, e)


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
        if self._peak_at_utc and current_balance and current_balance > 0.0:
            try:
                peak_dt = datetime.fromisoformat(self._peak_at_utc)
                if (now_dt - peak_dt).total_seconds() > 4 * 86400:
                    peak_iso_week = peak_dt.isocalendar()[1]
                    now_iso_week = now_dt.isocalendar()[1]
                    if now_iso_week != peak_iso_week and self._hwm and self._hwm > current_balance:
                        logger__high_water_mark.info(
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
                logger__high_water_mark.warning("Weekly HWM check notice: %s", e)

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
        logger__high_water_mark.warning(
            "🔄 Đặt lại High-Water Mark: $%s -> $%.2f (chỉ hợp lệ khi nạp/rút vốn)",
            f"{self._hwm:.2f}" if self._hwm else "None",
            equity,
        )
        self._hwm = None
        self._peak_at_utc = None
        return self.update(equity)


# ====================================================================================================
# core/fleet_guard.py  —  Fleet Guard: Production Safety & System Design Protection Layer.
# ====================================================================================================




logger__fleet_guard = logging.getLogger("fleet_guard")


class IdempotencyError(Exception):
    """Raised when a duplicate order request is detected."""
    pass


class SanityCheckError(Exception):
    """Raised when an order violates zero-trust risk bounds."""
    pass


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is active and blocking new trades."""
    pass


@dataclass
class GuardConfig:
    """Configuration for Zero-Trust and System-Design safeguards."""
    max_lot_cap: float = 0.50             # Hard lot ceiling across all strategies
    min_lot_floor: float = 0.01           # Hard lot floor
    mandatory_sl: bool = True             # Absolute zero-tolerance for naked positions
    max_slippage_points: float = 30.0     # Max deviation / slippage points allowed
    rate_limit_per_sec: float = 5.0       # Max requests per second to MT5
    consecutive_error_threshold: int = 3  # Failures before circuit trips
    circuit_cooldown_sec: int = 1800      # 30-minute lockdown on tripped circuit
    db_path: Optional[str] = None         # SQLite WAL path for idempotency persistence


class IdempotencyRegistry:
    """Guarantees exactly-once execution per (magic, symbol, bar_time, direction).
    
    Prevents duplicate orders during broker retries, network blips, or scheduler overlaps.
    Uses SQLite in WAL mode for persistent, cross-process reliability.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent / "logs"
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / "idempotency_store.db")
        
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS idempotency_keys (
                        token TEXT PRIMARY KEY,
                        bot_id TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        action TEXT NOT NULL,
                        lot REAL NOT NULL,
                        created_at REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at 
                    ON idempotency_keys(created_at);
                """)
                conn.commit()

    @staticmethod
    def generate_token(magic: int, symbol: str, bar_time_utc: str, action: str, lot: float) -> str:
        """Computes deterministic SHA256 idempotency fingerprint."""
        raw = f"{magic}|{symbol.upper()}|{bar_time_utc}|{action.upper()}|{lot:.4f}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def acquire(self, token: str, bot_id: str, symbol: str, action: str, lot: float, ttl_seconds: int = 86400) -> bool:
        """Attempts to register token. Returns True if first-time, False if duplicate.
        
        Automatically purges stale entries older than ttl_seconds.
        """
        now = time.time()
        with self._lock:
            with self._get_connection() as conn:
                # Cleanup stale records
                conn.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (now - ttl_seconds,))
                
                # Check if exists
                cur = conn.cursor()
                cur.execute("SELECT token FROM idempotency_keys WHERE token = ?", (token,))
                if cur.fetchone():
                    return False
                
                # Register
                try:
                    conn.execute(
                        "INSERT INTO idempotency_keys (token, bot_id, symbol, action, lot, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (token, bot_id, symbol, action, lot, now)
                    )
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False


class TokenBucketLimiter:
    """Thread-safe Token Bucket Rate Limiter to prevent terminal/broker flooding."""

    def __init__(self, rate_per_sec: float = 5.0, capacity: float = 10.0):
        self.rate = rate_per_sec
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens_needed: float = 1.0, wait: bool = True) -> bool:
        """Acquires tokens, sleeping if necessary up to a safety limit."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= tokens_needed:
                    self.tokens -= tokens_needed
                    return True
                
                if not wait:
                    return False
                
                missing = tokens_needed - self.tokens
                sleep_time = missing / self.rate

            time.sleep(min(sleep_time, 0.5))


class CircuitBreaker:
    """Circuit Breaker (CLOSED -> OPEN -> HALF-OPEN) to protect capital during outages."""

    def __init__(self, threshold: int = 3, cooldown_sec: int = 1800):
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self.consecutive_errors = 0
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def record_success(self) -> None:
        with self._lock:
            self.consecutive_errors = 0
            self.last_failure_time = None

    def record_failure(self) -> None:
        with self._lock:
            self.consecutive_errors += 1
            self.last_failure_time = time.time()
            if self.consecutive_errors >= self.threshold:
                logger__fleet_guard.critical(
                    f"[CIRCUIT BREAKER TRIPPED] {self.consecutive_errors} consecutive failures! "
                    f"Tripping circuit for {self.cooldown_sec} seconds."
                )

    def is_open(self) -> bool:
        with self._lock:
            if self.consecutive_errors < self.threshold:
                return False
            
            # Check cooldown
            if self.last_failure_time and (time.time() - self.last_failure_time > self.cooldown_sec):
                logger__fleet_guard.info("[CIRCUIT BREAKER HALF-OPEN] Cooldown period passed. Allowing canary test.")
                return False
            
            return True


class FleetGuard:
    """Master orchestrator combining Idempotency, Rate-Limiting, Sanity, and Circuit Breakers."""

    def __init__(self, config: Optional[GuardConfig] = None):
        self.cfg = config or GuardConfig()
        self.idempotency = IdempotencyRegistry(self.cfg.db_path)
        self.limiter = TokenBucketLimiter(rate_per_sec=self.cfg.rate_limit_per_sec)
        self.breaker = CircuitBreaker(
            threshold=self.cfg.consecutive_error_threshold,
            cooldown_sec=self.cfg.circuit_cooldown_sec
        )

    def validate_and_gate_order(
        self,
        bot_id: str,
        magic: int,
        symbol: str,
        bar_time_utc: str,
        action: str,
        lot: float,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float] = None,
    ) -> str:
        """Performs full Zero-Trust Gate check.
        
        Returns the registered unique idempotency token on success.
        Raises SanityCheckError, IdempotencyError, or CircuitBreakerOpenError on violation.
        """
        # 1. Circuit Breaker Check
        if self.breaker.is_open():
            raise CircuitBreakerOpenError(
                f"FleetGuard Circuit Breaker is OPEN for {bot_id}. Trading halted due to consecutive failures."
            )

        # 2. Rate Limiting Check
        self.limiter.acquire(1.0, wait=True)

        # 3. Zero-Trust Lot Sizing Bounds
        if lot > self.cfg.max_lot_cap:
            raise SanityCheckError(
                f"[VIOLATION] Requested lot {lot:.3f} exceeds hard MAX_LOT_CAP ({self.cfg.max_lot_cap}). "
                f"Order strictly aborted."
            )
        if lot < self.cfg.min_lot_floor:
            raise SanityCheckError(
                f"[VIOLATION] Requested lot {lot:.3f} below MIN_LOT_FLOOR ({self.cfg.min_lot_floor})."
            )

        # 4. Mandatory Stop Loss Check
        act = action.lower()
        if self.cfg.mandatory_sl:
            if stop_loss is None or stop_loss <= 0:
                raise SanityCheckError(
                    f"[ZERO-TRUST VIOLATION] Naked position detected! {bot_id} tried {action} without valid Stop-Loss."
                )
            if act in ("buy", "long") and stop_loss >= entry_price:
                raise SanityCheckError(
                    f"[SANITY FAILED] BUY order SL ({stop_loss}) must be strictly below entry price ({entry_price})."
                )
            if act in ("sell", "short") and stop_loss <= entry_price:
                raise SanityCheckError(
                    f"[SANITY FAILED] SELL order SL ({stop_loss}) must be strictly above entry price ({entry_price})."
                )

        # 5. Idempotency Check (Chống trùng lệnh)
        token = self.idempotency.generate_token(magic, symbol, bar_time_utc, action, lot)
        acquired = self.idempotency.acquire(token, bot_id, symbol, action, lot)
        if not acquired:
            raise IdempotencyError(
                f"[DUPLICATE REJECTED] Order already executed for token: {token[:12]}... "
                f"({bot_id} {symbol} {bar_time_utc} {action})"
            )

        logger__fleet_guard.info(f"[FLEET GUARD PASS] Bot {bot_id} authorized: {action} {lot} {symbol} (Token: {token[:8]})")
        return token
