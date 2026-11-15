"""Golden test (Phần 3, Bước 4): gate trade_mode (symbol_info + SYMBOL_TRADE_MODE_FULL) ở đầu vòng pod của scan_and_route.

Hai lớp:
  * đơn vị: _symbol_trade_gate(actual_symbol) -> (skip, sym_info) trên nhiều dạng symbol_info / lỗi MT5;
  * xuyên scan_and_route_state_proposals (đồng hồ cố định Thứ Tư 14:00 UTC, 1 pod giả, dừng ngay sau gate bằng
    is_market_open=False): gate chặn thì KHÔNG gọi is_market_open; gate qua thì gọi đúng 1 lần; get_rates không bao giờ được gọi.
ADR-004 (fail-closed): ngoại lệ MT5 => skip=True, info=None; không còn kế thừa sym_info của pod trước.
Sinh fixture từ mã TRƯỚC khi chuyển sang L1 (đã sinh lại sau ADR-004 chỉ cho 2 kịch bản đổi + 1 kịch bản mới):  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_trade_mode_gate.py
Chỉ dùng test double; không gửi lệnh thật.
"""
import json
import os
from datetime import datetime as _real_dt, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import MetaTrader5 as _mt5
import pytest

import us_federation_quant.Architecter.live_federation_runner as runner_mod
from us_federation_quant.Architecter.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "trade_mode_gate.json")
RUNNER = "us_federation_quant.Architecter.live_federation_runner"
FULL = _mt5.SYMBOL_TRADE_MODE_FULL


def _label(info):
    if info is None:
        return "None"
    return f"obj(trade_mode={getattr(info, 'trade_mode', 'MISSING')})"


def _gate(table, raises=None, delete_full_const=False):
    calls = []

    def fake(sym):
        calls.append(sym)
        if raises:
            raise raises
        return table

    if delete_full_const:
        with patch("MetaTrader5.SYMBOL_TRADE_MODE_FULL", 4, create=True):
            delattr(_mt5, "SYMBOL_TRADE_MODE_FULL")
            with patch("MetaTrader5.symbol_info", side_effect=fake):
                skip, info = runner_mod._symbol_trade_gate("EURUSDm")
    else:
        with patch("MetaTrader5.symbol_info", side_effect=fake):
            skip, info = runner_mod._symbol_trade_gate("EURUSDm")
    return {"skip": skip, "info": _label(info), "symbol_info_calls": calls}


class _FrozenDT(_real_dt):
    @classmethod
    def now(cls, tz=None):
        return _real_dt(2026, 11, 11, 14, 0, tzinfo=tz or timezone.utc)


def _scan(table, raises=None):
    r = RT(initial_capital_usd=9000.0)
    pod = SimpleNamespace(state_id="STATE_21", state_name="Test Pod", primary_asset="EURUSD", timeframe="H1")
    r.hub = MagicMock()
    r.hub.states_registry.get_all_active_states.return_value = [pod]
    r.hub.fed.allocate_carver_state_quotas.return_value = {"quotas": {}, "cash_vol_targets": {}, "idm": 1.0, "policy": "NEUTRAL"}
    mgr = MagicMock()
    mgr.resolve_symbol.side_effect = lambda s: s + "m"
    mgr.is_market_open.return_value = False
    r.mt5_mgr = mgr
    calls = []

    def fake(sym):
        calls.append(sym)
        if raises:
            raise raises
        return table

    with patch(f"{RUNNER}.datetime", _FrozenDT), patch("MetaTrader5.symbol_info", side_effect=fake):
        res = r.scan_and_route_state_proposals(account_equity=10_000.0)
    return {"result": res, "symbol_info_calls": calls,
            "is_market_open_calls": [c.args[0] for c in mgr.is_market_open.call_args_list],
            "get_rates_calls": mgr.get_rates.call_count}


def _current():
    full = SimpleNamespace(trade_mode=FULL)
    closeonly = SimpleNamespace(trade_mode=3)
    notmode = SimpleNamespace()
    return {
        "unit_info_none_skips": _gate(None),
        "unit_full_passes": _gate(full),
        "unit_closeonly_skips": _gate(closeonly),
        "unit_missing_trade_mode_skips": _gate(notmode),
        "unit_symbol_info_raises_fail_closed": _gate(None, raises=RuntimeError("ipc")),
        "unit_full_const_missing_fail_closed": _gate(full, delete_full_const=True),
        "scan_gate_blocks_info_none": _scan(None),
        "scan_gate_blocks_not_full": _scan(closeonly),
        "scan_gate_passes_full_reaches_market_open": _scan(full),
        "scan_gate_blocks_when_symbol_info_raises": _scan(None, raises=RuntimeError("ipc")),
    }


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
