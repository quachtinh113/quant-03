"""Golden test 4c: đọc lịch sử deal (history_deals_get) + gate vào lệnh (can_enter_trade) + theo dõi vị thế vừa đóng.

Đóng băng: kết quả (allowed, lý do), tham số từng lần gọi history_deals_get, trạng thái symbol_state/_tracked_open_tickets, log.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_deals_gate.py
Chỉ dùng test double; không gửi lệnh thật.
"""
import json
import logging
import os
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from us_federation_quant.Architecter.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "deals_gate.json")
NOW = 1_800_000_000.0


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, r):
        self.rows.append([r.levelname, r.getMessage()])


def deal(ticket, position_id, t, type_, entry, symbol="EURUSDm", profit=0.0, commission=0.0, swap=0.0, comment=""):
    return SimpleNamespace(ticket=ticket, position_id=position_id, time=t, type=type_, entry=entry, symbol=symbol,
                           profit=profit, commission=commission, swap=swap, comment=comment)


def _capture(fn):
    cap = _Cap()
    lg = logging.getLogger("USFederationQuant")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    try:
        return fn(), cap.rows
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)


def _gate(direction, deals, symbol="EURUSDm", symbol_state=None, raises=None, attrs=None):
    r = RT(initial_capital_usd=9000.0)
    r.symbol_state = dict(symbol_state or {})
    for k, v in (attrs or {}).items():
        setattr(r, k, v)
    calls = []

    def fake(a, b):
        calls.append([a.timestamp(), b.timestamp(), str(a.tzinfo), str(b.tzinfo)])
        if raises:
            raise raises
        return deals

    def run():
        with patch("MetaTrader5.history_deals_get", side_effect=fake):
            return r.can_enter_trade(symbol, direction, NOW)

    res, logs = _capture(run)
    return {"result": list(res), "calls": calls, "logs": logs}


def _track(tracked, current, deals_by_call, attrs=None, get_positions_raises=None, symbol_state=None):
    r = RT(initial_capital_usd=9000.0)
    r.symbol_state = {k: dict(v) for k, v in (symbol_state or {}).items()}
    r._tracked_open_tickets = {t: dict(p) for t, p in tracked.items()}
    for k, v in (attrs or {}).items():
        setattr(r, k, v)
    mgr = MagicMock()
    if get_positions_raises:
        mgr.get_positions.side_effect = get_positions_raises
    else:
        mgr.get_positions.return_value = [dict(p) for p in current]
    r.mt5_mgr = mgr
    seq = list(deals_by_call)
    calls = []

    def fake(a, b):
        calls.append([a.timestamp(), b.timestamp()])
        return seq.pop(0) if seq else None

    def run():
        with patch("MetaTrader5.history_deals_get", side_effect=fake):
            r.update_symbol_exit_tracking(NOW)

    _, logs = _capture(run)
    return {"symbol_state": r.symbol_state, "tracked": sorted(map(str, r._tracked_open_tickets)),
            "calls": calls, "logs": logs}


def _current():
    o = {}
    # ----------------------------------------------------------------- can_enter_trade
    closed = lambda tk, pid, ago, type_=1, profit=-5.0, sym="EURUSDm", entry=1: deal(tk, pid, NOW - ago, type_, entry, sym, profit)
    opened = lambda tk, pid, ago, type_=0, sym="EURUSDm": deal(tk, pid, NOW - ago - 100, type_, 0, sym)
    o["gate_deals_empty_ok"] = _gate("BUY", ())
    o["gate_cooldown_veto"] = _gate("BUY", (closed(1, 10, 300),))
    o["gate_cooldown_boundary_900_ok"] = _gate("BUY", (closed(1, 10, 900),))
    o["gate_other_symbol_ignored"] = _gate("BUY", (closed(1, 10, 100, sym="GBPUSDm"),))
    o["gate_future_deal_ignored"] = _gate("BUY", (closed(1, 10, -50),))
    o["gate_symbol_clean_match_no_m"] = _gate("BUY", (closed(1, 10, 100, sym="EURUSD"),), symbol="EURUSDm")
    o["gate_entry_inout_3_counts"] = _gate("BUY", (closed(1, 10, 100, entry=3),))
    o["gate_entry_in_not_closed"] = _gate("BUY", (opened(1, 10, 100),))
    two_sl_buy = (opened(1, 10, 5000, 0), opened(2, 11, 4000, 0),
                  closed(3, 10, 3000, type_=1, profit=-6.0), closed(4, 11, 1000, type_=1, profit=-4.0))
    o["gate_2sl_lockout_buy_blocks_buy"] = _gate("BUY", two_sl_buy)
    o["gate_2sl_lockout_buy_allows_sell"] = _gate("SELL", two_sl_buy)
    o["gate_2sl_but_one_profit_ok"] = _gate("BUY", (opened(1, 10, 5000, 0), opened(2, 11, 4000, 0),
                                                   closed(3, 10, 3000, type_=1, profit=6.0), closed(4, 11, 1000, type_=1, profit=-4.0)))
    o["gate_2sl_lockout_expired_ok"] = _gate("BUY", (opened(1, 10, 20000, 0), opened(2, 11, 19000, 0),
                                                    closed(3, 10, 8000, type_=1, profit=-6.0), closed(4, 11, 7500, type_=1, profit=-4.0)))
    o["gate_dir_fallback_from_close_type"] = _gate("SELL", (closed(3, 10, 3000, type_=0, profit=-6.0),
                                                          closed(4, 11, 1000, type_=0, profit=-4.0)))
    o["gate_sort_by_time_then_ticket"] = _gate("BUY", (closed(9, 10, 1000), closed(2, 11, 1000), closed(5, 12, 4000)))
    o["gate_custom_cooldown_attr"] = _gate("BUY", (closed(1, 10, 100),), attrs={"COOLDOWN_AFTER_EXIT_SEC": 50.0})
    # ---- đường dự phòng (deals None) dùng symbol_state trong bộ nhớ
    fb = {"EURUSD": {"last_exit_ts": NOW - 300}}
    o["gate_fallback_none_cooldown"] = _gate("BUY", None, symbol_state=fb)
    o["gate_fallback_exception_cooldown"] = _gate("BUY", None, symbol_state=fb, raises=RuntimeError("ipc"))
    o["gate_fallback_lock_buy"] = _gate("BUY", None, symbol_state={"EURUSD": {"last_exit_ts": 0.0, "lock_buy_until": NOW + 500}})
    o["gate_fallback_lock_sell_blocks_sell"] = _gate("SELL", None, symbol_state={"EURUSD": {"last_exit_ts": 0.0, "lock_sell_until": NOW + 500}})
    o["gate_fallback_lock_sell_allows_buy"] = _gate("BUY", None, symbol_state={"EURUSD": {"last_exit_ts": 0.0, "lock_sell_until": NOW + 500}})
    o["gate_fallback_no_state_ok"] = _gate("BUY", None)
    # ----------------------------------------------------------------- update_symbol_exit_tracking
    pos = lambda t, sym="EURUSDm", typ="BUY": {"ticket": t, "symbol": sym, "type": typ}
    sl_deal = lambda t, pid=None, profit=-8.0, comment="sl 1.1": deal(100 + t, pid or t, NOW - 5, 1, 1, "EURUSDm", profit, comment=comment)
    o["track_nothing_tracked"] = _track({}, [pos(1)], [])
    o["track_still_open_no_deal_lookup"] = _track({1: pos(1)}, [pos(1)], [])
    o["track_closed_sl_buy_first"] = _track({1: pos(1)}, [], [(sl_deal(1),)])
    o["track_closed_two_sl_buy_locks"] = _track({1: pos(1), 2: pos(2)}, [], [(sl_deal(1),), (sl_deal(2),)])
    o["track_closed_two_sl_sell_locks"] = _track({1: pos(1, typ="SELL"), 2: pos(2, typ="SELL")}, [], [(sl_deal(1),), (sl_deal(2),)])
    o["track_type_int_zero_is_buy"] = _track({1: {"ticket": 1, "symbol": "EURUSDm", "type": 0}}, [], [(sl_deal(1),)])
    o["track_profit_resets_counters"] = _track({1: pos(1)}, [], [(sl_deal(1, profit=9.0, comment="tp"),)],
                                               symbol_state={"EURUSD": {"last_exit_ts": 1.0, "consec_sl_buy": 1, "consec_sl_sell": 1, "lock_buy_until": 0.0, "lock_sell_until": 0.0}})
    o["track_comment_sl_even_if_small_loss"] = _track({1: pos(1)}, [], [(sl_deal(1, profit=-0.1, comment="[sl]"),)])
    o["track_small_loss_no_sl_word_not_sl"] = _track({1: pos(1)}, [], [(sl_deal(1, profit=-0.4, comment="manual"),)])
    o["track_loss_over_half_dollar_is_sl"] = _track({1: pos(1)}, [], [(sl_deal(1, profit=-0.6, comment="manual"),)])
    o["track_commission_swap_included"] = _track({1: pos(1)}, [], [(deal(101, 1, NOW, 1, 1, "EURUSDm", -0.2, commission=-0.2, swap=-0.2, comment="x"),)])
    o["track_deals_none"] = _track({1: pos(1)}, [], [None])
    o["track_deals_empty"] = _track({1: pos(1)}, [], [()])
    o["track_wrong_position_id"] = _track({1: pos(1)}, [], [(sl_deal(1, pid=999),)])
    o["track_entry_not_out_ignored"] = _track({1: pos(1)}, [], [(deal(101, 1, NOW, 1, 3, "EURUSDm", -8.0, comment="sl"),)])
    o["track_custom_max_consec_1"] = _track({1: pos(1)}, [], [(sl_deal(1),)], attrs={"MAX_CONSECUTIVE_SL_SAME_DIR": 1})
    o["track_get_positions_raises"] = _track({1: pos(1)}, [], [], get_positions_raises=RuntimeError("ipc"))
    o["track_new_tracked_replaced"] = _track({1: pos(1)}, [pos(1), pos(7)], [])
    return o


def test_generate_or_match_golden():
    current = json.loads(json.dumps(_current(), sort_keys=True, default=str))
    if os.environ.get("GENERATE_GOLDEN") == "1":
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        json.dump(current, open(GOLDEN, "w", encoding="utf-8"), indent=1, ensure_ascii=False, sort_keys=True)
        pytest.skip("golden đã được sinh")
    golden = json.load(open(GOLDEN, encoding="utf-8"))
    for k in golden:
        assert current[k] == golden[k], f"golden lệch ở: {k}"
    assert set(current) == set(golden)
