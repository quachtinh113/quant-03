"""Golden test (đóng băng hành vi) cho nhóm quản lý thoát lệnh / thời gian của runner:
breakeven, profit ladder, two-tier exit, reconcile US30, Friday EOD flat, liquidation readiness,
weekend sweeper và các hàm giờ/phiên (DST, curfew, EOD window, HK50, toxic hour).

Fixture được sinh từ mã TRƯỚC khi di chuyển sang layers/l4_risk.py:
    GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_l4_exits.py
Không có MT5 thật: MetaTrader5, mt5_mgr và telemetry đều là test double; không gửi lệnh.
Ghi cả THỨ TỰ các lời gọi (close/modify) vì lát chuyển sau sẽ đổi "quyết định rồi mới thực thi".
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from us_federation_quant.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "l4_exits.json")
UTC = timezone.utc


# --------------------------------------------------------------------------- doubles
def _sym_info(**kw):
    d = dict(point=0.00001, digits=5, trade_tick_value=1.0, trade_tick_size=0.00001,
             spread=10, trade_mode=4)
    d.update(kw)
    return SimpleNamespace(**d)


def _fake_mt5(infos=None, ticks=None, positions=None):
    infos = infos or {}
    ticks = ticks or {}
    return SimpleNamespace(
        SYMBOL_TRADE_MODE_FULL=4,
        symbol_info=lambda s: infos.get(s, infos.get("*", _sym_info())),
        symbol_info_tick=lambda s: ticks.get(s, ticks.get("*")),
        positions_get=lambda *a, **k: positions,
    )


def _runner(positions, specs=None, market_open=None, close_fail=()):
    r = RT(initial_capital_usd=9000.0)
    mgr = MagicMock()
    mgr.get_positions.return_value = [dict(p) for p in positions]
    mgr.resolve_symbol.side_effect = lambda s: s
    default_spec = {"digits": 5, "point": 0.00001, "tick_size": 0.00001, "tick_value": 1.0}
    mgr.get_symbol_spec.side_effect = lambda s: (specs or {}).get(s, default_spec)
    mgr.is_market_open.side_effect = lambda s: True if market_open is None else bool(market_open.get(s, market_open.get("*", True)))
    mgr.modify_position_sltp.side_effect = lambda **kw: {"success": True, "ticket": kw.get("ticket")}
    mgr.close_position.side_effect = (
        lambda ticket=None, **kw: {"success": ticket not in close_fail, "ticket": ticket, "error": "x"}
    )
    r.mt5_mgr = mgr
    r.telemetry = MagicMock()
    r._profit_ladder_locked_tickets = set()
    r._tier2_locked_tickets = set()
    return r


def _calls(mock):
    return [[list(c.args), {k: v for k, v in c.kwargs.items()}] for c in mock.call_args_list]


def _snap(r, returned, extra=None):
    out = {
        "returned": returned,
        "modify_calls": _calls(r.mt5_mgr.modify_position_sltp),
        "close_calls": _calls(r.mt5_mgr.close_position),
        "ladder_locked": sorted(map(str, r._profit_ladder_locked_tickets)),
        "tier2_locked": sorted(map(str, r._tier2_locked_tickets)),
    }
    if extra:
        out.update(extra)
    return json.loads(json.dumps(out, sort_keys=True, default=str))


def _pos(ticket, symbol, typ, entry, cur, profit, sl=0.0, tp=0.0, vol=0.10, swap=0.0, **kw):
    d = {"ticket": ticket, "symbol": symbol, "type": typ, "price_open": entry,
         "price_current": cur, "profit": profit, "sl": sl, "tp": tp, "volume": vol, "swap": swap}
    d.update(kw)
    return d


# --------------------------------------------------------------------------- scenarios
def sc_breakeven():
    ps = [
        _pos(1, "EURUSDm", "BUY", 1.1000, 1.1020, 13.0, sl=1.0950),      # profit>=12, dời lên
        _pos(2, "EURUSDm", "BUY", 1.1000, 1.1020, 13.0, sl=1.1005),      # SL đã cao hơn -> không dời
        _pos(3, "EURUSDm", "SELL", 1.1000, 1.0980, 12.0, sl=0.0),        # SELL, sl=0
        _pos(4, "EURUSDm", "SELL", 1.1000, 1.0990, 1.0, sl=1.1050, tp=1.0980),  # 50% TP
        _pos(5, "EURUSDm", "BUY", 1.1000, 1.1002, 5.0, sl=1.0950, tp=1.1100),   # chưa đủ
        _pos(6, "USDJPYm", "BUY", 150.00, 150.30, 20.0, sl=149.0),       # digits 3
        _pos(7, "EURUSDm", "BUY", 0.0, 1.1, 50.0),                       # entry<=0 bỏ qua
        _pos(8, "EURUSDm", "BUY", 1.1000, 1.1020, 13.0, sl=1.0950, type_int=0),
        _pos(9, "NOINFO", "BUY", 1.1, 1.2, 50.0, sl=1.0),                # symbol_info None
    ]
    infos = {"*": _sym_info(), "USDJPYm": _sym_info(point=0.001, digits=3, trade_tick_size=0.001),
             "NOINFO": None}
    r = _runner(ps)
    with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(infos)}):
        ret = r.check_and_apply_breakeven_lock()
    return _snap(r, ret)


def sc_ladder():
    ps = [
        _pos(1, "EURUSDm", "BUY", 1.1000, 1.1060, 16.0, sl=1.0950, tp=1.1100),   # tier 3
        _pos(2, "EURUSDm", "SELL", 1.1000, 1.0940, 16.0, sl=1.1050, tp=1.0900),
        _pos(3, "EURUSDm", "BUY", 1.1000, 1.1040, 9.0, sl=1.0950, tp=1.1100),    # tier 2
        _pos(4, "EURUSDm", "SELL", 1.1000, 1.0960, 9.0, sl=0.0, tp=0.0),
        _pos(5, "EURUSDm", "BUY", 1.1000, 1.1020, 5.0, sl=1.0950, tp=1.1100),    # tier 1
        _pos(6, "EURUSDm", "SELL", 1.1000, 1.0985, 1.0, sl=1.1050, tp=1.0950),   # 40% TP
        _pos(7, "EURUSDm", "BUY", 1.1000, 1.1003, 1.0, sl=1.0950, tp=1.1100),    # không đủ
        _pos(8, "EURUSDm", "BUY", 1.1000, 1.1060, 5.0, swap=11.5, sl=1.0950),    # swap kéo lên tier 3
        _pos(9, "NOINFO", "BUY", 1.1000, 1.1060, 16.0, sl=1.0950, tp=1.1100),    # dùng get_symbol_spec
        _pos(10, "EURUSDm", "BUY", 0.0, 1.0, 99.0),                              # bỏ qua
    ]
    infos = {"*": _sym_info(), "NOINFO": None}
    r = _runner(ps)
    with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(infos)}):
        ret = r.manage_multi_tier_profit_ladder()
    return _snap(r, ret)


def sc_two_tier():
    ps = [
        _pos(1, "EURUSDm", "BUY", 1.1000, 1.1100, 30.0, sl=1.0950, vol=0.10),    # partial 50%
        _pos(2, "EURUSDm", "SELL", 1.1000, 1.0900, 30.0, sl=1.1050, vol=0.01),   # min volume
        _pos(3, "EURUSDm", "BUY", 1.1000, 1.1050, 18.0, sl=1.0950, vol=0.10),    # tier2 lock BUY
        _pos(4, "EURUSDm", "SELL", 1.1000, 1.0950, 18.0, sl=0.0, vol=0.10),      # tier2 lock SELL
        _pos(5, "EURUSDm", "BUY", 1.1000, 1.1100, 30.0, sl=1.0950, vol=0.10),    # đóng thất bại
        _pos(6, "EURUSDm", "BUY", 1.1000, 1.1100, 20.0, sl=1.0950, vol=0.10),    # tier1 đã xong
        _pos(7, "EURUSDm", "BUY", 1.1000, 1.1005, 3.0, sl=1.0950, vol=0.10),     # không làm gì
    ]
    r = _runner(ps, close_fail={5})
    state = {"6": {"tier1_closed": True}, "999": {"tier1_closed": True}}  # 999 phải bị dọn
    saved = []
    r._load_two_tier_state = lambda: json.loads(json.dumps(state))
    r._save_two_tier_state = lambda s: saved.append(
        {k: {kk: vv for kk, vv in v.items() if kk != "time"} for k, v in s.items()})
    ret = r.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)
    return _snap(r, ret, {"saved_state": saved})


def sc_reconcile():
    r = _runner([
        _pos(1, "US30m", "BUY", 40000, 40100, -80.0),
        _pos(2, "US30m", "BUY", 40000, 40100, -30.0),
        _pos(3, "US30m", "BUY", 40000, 40100, -10.0),
        _pos(4, "US30m", "SELL", 40000, 40100, 5.0),
    ])
    ret = r.reconcile_index_duplicate_derisking()
    r2 = _runner([_pos(1, "US30m", "BUY", 40000, 40100, -10.0)])
    ret2 = r2.reconcile_index_duplicate_derisking()
    return {"multi": _snap(r, ret), "single": _snap(r2, ret2)}


def sc_friday_eod():
    out = {}
    ps = [_pos(1, "EURUSDm", "BUY", 1.1, 1.1, -3.0), _pos(2, "UK100m", "BUY", 8000, 8000, 4.0),
          _pos(3, "XAUUSDm", "SELL", 2000, 2000, 1.0)]
    # now_utc=None -> thanh lý toàn bộ
    r = _runner(ps, close_fail={3})
    with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(positions=None)}):
        out["all"] = _snap(r, r.enforce_friday_eod_flat())
    # now_utc truyền vào: phân tầng theo mã (Thứ Sáu 20:20 UTC -> chỉ chỉ số)
    r = _runner(ps)
    with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(positions=None)}):
        out["tiered_2020"] = _snap(r, r.enforce_friday_eod_flat(datetime(2026, 11, 6, 20, 20, tzinfo=UTC)))
    r = _runner(ps)
    with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(positions=None)}):
        out["tiered_2145"] = _snap(r, r.enforce_friday_eod_flat(datetime(2026, 11, 6, 21, 45, tzinfo=UTC)))
    # vị thế đối tượng từ mt5.positions_get
    objs = [SimpleNamespace(ticket=11, symbol="EURUSDm", profit=1.5),
            SimpleNamespace(ticket=None, symbol="X", profit=0.0)]
    r = _runner([])
    with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(positions=objs)}):
        out["objects"] = _snap(r, r.enforce_friday_eod_flat())
    r = _runner([])
    with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(positions=None)}):
        out["empty"] = _snap(r, r.enforce_friday_eod_flat())
    return out


def sc_readiness():
    now = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    ts = now.timestamp()
    out = {}

    def run(name, symbol, ticks, infos=None, market_open=None, preseed=None, warmup=600.0, now_utc=now):
        r = _runner([], market_open=market_open)
        saved = []
        r._symbol_reopen_first_seen_ts = dict(preseed or {})
        r._save_sweeper_reopen_state = lambda s: saved.append(dict(s))
        with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(infos or {}, ticks)}):
            res = r.check_symbol_liquidation_readiness(symbol, now_utc=now_utc, open_warmup_sec=warmup)
        out[name] = {"result": list(res), "saved": saved, "state": r._symbol_reopen_first_seen_ts}

    tk = lambda age, bid=1.10000, ask=1.10010: SimpleNamespace(time=ts - age, bid=bid, ask=ask)
    run("market_closed", "EURUSDm", {"*": tk(5)}, market_open={"EURUSDm": False})
    run("tick_none", "EURUSDm", {})
    run("trade_mode_not_full", "EURUSDm", {"*": tk(5)}, infos={"*": _sym_info(trade_mode=0)})
    run("tick_time_zero", "EURUSDm", {"*": SimpleNamespace(time=0, bid=1.1, ask=1.1001)})
    run("stale_tick", "EURUSDm", {"*": tk(300)}, preseed={"EURUSDm": ts - 5000})
    run("future_tick_offset", "EURUSDm", {"*": tk(-7200)})
    run("warmup_active", "EURUSDm", {"*": tk(5)})
    run("warmup_done_ready", "EURUSDm", {"*": tk(5)}, preseed={"EURUSDm": ts - 900})
    run("fx_spread_wide_major", "EURUSDm", {"*": tk(5, 1.10000, 1.10100)}, preseed={"EURUSDm": ts - 900})
    run("fx_spread_ok_cross", "GBPCHFm", {"*": tk(5, 1.10000, 1.10060)}, preseed={"GBPCHFm": ts - 900})
    run("fx_spread_wide_cross", "GBPCHFm", {"*": tk(5, 1.10000, 1.10090)}, preseed={"GBPCHFm": ts - 900})
    run("index_spread_wide", "UK100m", {"*": tk(5, 8000.0, 8008.0)}, preseed={"UK100m": ts - 900})
    run("index_spread_ok", "UK100m", {"*": tk(5, 8000.0, 8004.0)}, preseed={"UK100m": ts - 900})
    run("safety_ceiling", "EURUSDm", {"*": tk(5, 1.10000, 1.10500)}, preseed={"EURUSDm": ts - 2000})
    run("no_warmup_param", "EURUSDm", {"*": tk(5)}, warmup=0.0)
    return out


def sc_sweeper():
    out = {}

    def run(name, now, positions, market_open=None, preseed=None, ticks=None, close_fail=(), infos=None):
        r = _runner(positions, market_open=market_open, close_fail=close_fail)
        saved = []
        r._symbol_reopen_first_seen_ts = dict(preseed or {})
        r._save_sweeper_reopen_state = lambda s: saved.append(dict(s))
        ts = now.timestamp()
        tk = ticks or {"*": SimpleNamespace(time=ts - 5, bid=1.10000, ask=1.10010)}
        with patch.dict(sys.modules, {"MetaTrader5": _fake_mt5(infos or {}, tk, positions=None)}):
            ret = r.enforce_weekend_hold_sweeper(now_utc=now)
        out[name] = _snap(r, ret, {"saved": saved})

    wed = datetime(2026, 11, 11, 14, 0, tzinfo=UTC)
    h = lambda n, hours: (n - timedelta(hours=hours)).replace(tzinfo=UTC)
    p = lambda t, s, opened, pf=-2.0: {"ticket": t, "symbol": s, "profit": pf, "time": opened}
    run("over_12h_cut", wed, [p(1, "EURUSDm", h(wed, 13))])
    run("young_position", wed, [p(1, "EURUSDm", h(wed, 1))])
    run("no_positions", wed, [])
    sun = datetime(2026, 11, 8, 22, 30, tzinfo=UTC)
    run("sunday_warmup_defers", sun, [p(1, "EURUSDm", datetime(2026, 11, 6, 10, 0, tzinfo=UTC))])
    mon = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    run("monday_weekend_hold_closes", mon,
        [p(1, "EURUSDm", datetime(2026, 11, 6, 10, 0, tzinfo=UTC)),
         p(2, "GBPUSDm", int(datetime(2026, 11, 6, 11, 0, tzinfo=UTC).timestamp())),
         p(3, "EURUSDm", datetime(2026, 11, 9, 7, 30, tzinfo=UTC))],       # mở sau mốc -> không kẹt
        preseed={"EURUSDm": mon.timestamp() - 900, "GBPUSDm": mon.timestamp() - 900}, close_fail={2})
    run("monday_index_spread_defers", mon,
        [p(1, "UK100m", datetime(2026, 11, 6, 10, 0, tzinfo=UTC))],
        preseed={"UK100m": mon.timestamp() - 900},
        ticks={"*": SimpleNamespace(time=mon.timestamp() - 5, bid=8000.0, ask=8010.0)})
    fri = datetime(2026, 11, 6, 21, 45, tzinfo=UTC)   # 23:45 server (EST)
    run("friday_eod_market_open", fri, [p(1, "EURUSDm", h(fri, 3)), p(2, "UK100m", h(fri, 4))])
    run("friday_eod_market_closed", fri, [p(1, "EURUSDm", h(fri, 3))], market_open={"*": False})
    run("naive_time_is_utc", wed, [p(1, "EURUSDm", (wed - timedelta(hours=20)).replace(tzinfo=None))])
    return out


def sc_time_helpers():
    ranges = [datetime(2026, 3, 6, tzinfo=UTC), datetime(2026, 10, 30, tzinfo=UTC),
              datetime(2026, 11, 6, tzinfo=UTC), datetime(2026, 12, 31, tzinfo=UTC)]
    fns = {
        "us_dst": lambda t: RT.is_us_dst(t),
        "server_dt": lambda t: RT.get_mt5_server_datetime(t).isoformat(),
        "curfew": lambda t: RT.is_friday_or_weekend_curfew(t),
        "eod_none": lambda t: RT.is_friday_eod_flat_window(t),
        "eod_uk100": lambda t: RT.is_friday_eod_flat_window(t, symbol="UK100m"),
        "eod_eurusd": lambda t: RT.is_friday_eod_flat_window(t, symbol="EURUSDm"),
        "hk50": lambda t: RT.is_hk50_session_open(t),
        "weekly_open": lambda t: RT.get_last_weekly_open_utc(t).isoformat(),
    }
    out = {}
    for name, fn in fns.items():
        trans, last = [], object()
        for start in ranges:
            for i in range(4 * 96):
                t = start + timedelta(minutes=15 * i)
                v = fn(t)
                if name == "server_dt":
                    v = RT.get_mt5_server_datetime(t).hour - t.hour  # chỉ offset giờ
                if v != last:
                    trans.append([t.isoformat(), v])
                    last = v
        out[name] = trans
    out["toxic_hours"] = [h for h in range(24) if RT.is_toxic_hour(h)]
    return out


def _current():
    return {
        "breakeven": sc_breakeven(),
        "ladder": sc_ladder(),
        "two_tier": sc_two_tier(),
        "reconcile": sc_reconcile(),
        "friday_eod": sc_friday_eod(),
        "readiness": sc_readiness(),
        "sweeper": sc_sweeper(),
        "time_helpers": sc_time_helpers(),
    }


def test_generate_or_match_golden():
    current = json.loads(json.dumps(_current(), sort_keys=True, default=str))
    if os.environ.get("GENERATE_GOLDEN") == "1":
        os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
        with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=1, ensure_ascii=False, sort_keys=True)
        pytest.skip("golden đã được sinh")
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)
    for key in golden:
        assert current[key] == golden[key], f"golden lệch ở nhóm: {key}"
    assert set(current) == set(golden)
