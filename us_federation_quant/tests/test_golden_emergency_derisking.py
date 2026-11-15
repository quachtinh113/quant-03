"""Golden test cho đường kill-switch khẩn cấp (soft de-risking): trạng thái, directive, lời gọi broker, log.

Các kịch bản soft_* đóng băng API CŨ apply_soft_derisking (giữ lại, không còn nằm trên đường khẩn cấp).
ADR-003: manual_emergency_shutdown / update_equity chạm -12% giờ THANH LÝ TOÀN BỘ vị thế (cả lãi lẫn lỗ) qua CloseDirective;
lệnh đóng lỗi/ném ngoại lệ không chặn lệnh còn lại, quét lại tối đa 1 lượt. Chỉ 3 kịch bản manual_*/update_equity_red_with_broker
đổi so với golden cũ; mọi kịch bản khác giữ nguyên; các kịch bản liquidate_* là mới.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_emergency_derisking.py
Chỉ dùng test double; không gửi lệnh thật.
"""
import json
import logging
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from us_federation_quant.layers.l4_risk import FederalMasterKillSwitch
from us_federation_quant.layers.l5_execution import execute_directives

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "emergency_derisking.json")
T0 = 1_800_000_000.0


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, r):
        self.rows.append([r.levelname, r.getMessage()])


def _spec(sym):
    return {"point": 0.00001 if "JPY" not in sym else 0.001, "digits": 5 if "JPY" not in sym else 3}


def _connector(with_spec=True, with_modify=True, positions=None, positions_attr=None):
    names = []
    if with_spec:
        names.append("get_symbol_spec")
    if with_modify:
        names.append("modify_position_sltp")
    if positions is not None:
        names.append("get_positions")
    c = MagicMock(spec=names + ["close_position"]) if not positions_attr else MagicMock(spec=names + ["positions", "close_position"])
    if with_spec:
        c.get_symbol_spec.side_effect = _spec
    if with_modify:
        c.modify_position_sltp.side_effect = lambda **kw: {"success": True, "ticket": kw["ticket"]}
    c.close_position.side_effect = lambda **kw: {"success": True, "ticket": kw["ticket"]}
    if positions is not None:
        c.get_positions.return_value = positions
    if positions_attr:
        c.positions = positions_attr
    return c


def _calls(c):
    out = {}
    for name in ("modify_position_sltp", "close_position", "get_symbol_spec", "get_positions"):
        if hasattr(c, name) and isinstance(getattr(c, name), MagicMock):
            out[name] = [[list(x.args), dict(x.kwargs)] for x in getattr(c, name).call_args_list]
    return out


POS = [
    {"ticket": 1001, "symbol": "EURUSD", "type": "BUY", "price_open": 1.10000, "profit": 50.0},
    {"ticket": 1002, "symbol": "GBPUSD", "type": "SELL", "price_open": 1.30000, "profit": 35.0},
    {"ticket": 1003, "symbol": "USDJPY", "type": "BUY", "price_open": 155.000, "profit": -45.0},
    {"ticket": 1004, "symbol": "USDJPY", "type": 0, "open_price": 150.250, "profit": 0.01},
    {"ticket": 1005, "symbol": "EURUSD", "type": "1", "price_open": 1.20000, "profit": 10.0},
    {"ticket": 1006, "symbol": "EURUSD", "type": "BUY", "price_open": 1.10000, "profit": 0.0},
]


def _l5_executor(connector):
    return lambda dirs: execute_directives(SimpleNamespace(mt5_mgr=connector), dirs).captured


def _soft(name, positions, use_executor=False, **ckw):
    ks = FederalMasterKillSwitch()
    c = _connector(**ckw) if ckw is not None and ckw.get("__none__") is None else None
    cap = _Cap()
    lg = logging.getLogger("USFederationQuant" if use_executor else "FederalMasterKillSwitch")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    try:
        with patch("time.time", return_value=T0):
            res = ks.apply_soft_derisking(positions, broker_connector=c,
                                          executor=_l5_executor(c) if use_executor else None)
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)
    return {"result": res, "locked": ks.is_locked, "freeze_until": ks.freeze_until,
            "calls": _calls(c) if c is not None else None, "logs": cap.rows}


def _soft_no_connector(positions, mt5_info):
    ks = FederalMasterKillSwitch()
    cap = _Cap()
    lg = logging.getLogger("FederalMasterKillSwitch")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    try:
        with patch("time.time", return_value=T0), patch("MetaTrader5.symbol_info", return_value=mt5_info):
            res = ks.apply_soft_derisking(positions, broker_connector=None)
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)
    return {"result": res, "logs": cap.rows}


def _manual(connector, reason="Simulated CRO stop", use_executor=False):
    ks = FederalMasterKillSwitch()
    ks.peak_equity, ks.current_equity = 10_000.0, 9_000.0
    with patch("time.time", return_value=T0):
        d = ks.manual_emergency_shutdown(reason, broker_connector=connector,
                                         executor=_l5_executor(connector) if use_executor else None)
    return {"directive": {k: v for k, v in vars(d).items()}, "locked": ks.is_locked, "freeze_until": ks.freeze_until,
            "history": len(ks.incident_history), "calls": _calls(connector) if connector is not None else None}


def _update_equity_red(connector, use_executor=False):
    ks = FederalMasterKillSwitch()
    with patch("time.time", return_value=T0):
        ks.update_equity(10_000.0)
        d = ks.update_equity(8_700.0, broker_connector=connector,
                             executor=_l5_executor(connector) if use_executor else None)   # -13% <= -12%
    return {"directive": {k: v for k, v in vars(d).items()}, "locked": ks.is_locked,
            "calls": _calls(connector) if connector is not None else None}


def _liquidate(positions, close_fn=None, positions_after=None, use_executor=False):
    """ADR-003: manual_emergency_shutdown -> thanh lý. close_fn(ticket, n) -> dict|raise (n = lần gọi thứ n cho ticket đó)."""
    c = _connector(positions=positions)
    seq = [list(positions)] + ([list(positions_after)] if positions_after is not None else [])
    c.get_positions.side_effect = lambda: (seq.pop(0) if len(seq) > 1 else seq[0])
    counts = {}

    def _close(**kw):
        t = kw["ticket"]
        counts[t] = counts.get(t, 0) + 1
        return close_fn(t, counts[t]) if close_fn else {"success": True, "ticket": t}

    c.close_position.side_effect = _close
    rt = SimpleNamespace(mt5_mgr=c, telemetry=MagicMock())
    ks = FederalMasterKillSwitch()
    ks.peak_equity, ks.current_equity = 10_000.0, 8_700.0
    plan_box = {}
    orig = ks.apply_emergency_liquidation

    def spy(*a, **k):
        plan_box["plan"] = orig(*a, **k)
        return plan_box["plan"]

    ks.apply_emergency_liquidation = spy
    with patch("time.time", return_value=T0):
        ks.manual_emergency_shutdown("stress", broker_connector=c,
                                     executor=(lambda dirs: execute_directives(rt, dirs).captured) if use_executor else None)
    return {"plan": plan_box["plan"], "locked": ks.is_locked, "freeze_until": ks.freeze_until,
            "close_calls": [kw["ticket"] for kw in [x.kwargs for x in c.close_position.call_args_list]],
            "modify_calls": c.modify_position_sltp.call_count,
            "alerts": [k.kwargs["subject"] for k in rt.telemetry.broadcast_critical_alert.call_args_list] if use_executor else None}


def _fail(t, n):
    return {"success": False, "error": "requote", "retcode": 10004}


def _liquidation_scenarios(use_executor):
    P = POS[:3]
    def fail_1002(t, n):
        return _fail(t, n) if t == 1002 else {"success": True, "ticket": t}
    def fail_1002_first(t, n):
        return _fail(t, n) if (t == 1002 and n == 1) else {"success": True, "ticket": t}
    def raise_1002(t, n):
        if t == 1002:
            raise RuntimeError("ipc down")
        return {"success": True, "ticket": t}
    return {
        "liquidate_all_ok_profit_and_loss": _liquidate(P, use_executor=use_executor),
        "liquidate_one_fails_others_continue_retry_fails": _liquidate(P, fail_1002, use_executor=use_executor),
        "liquidate_one_raises_others_continue": _liquidate(P, raise_1002, use_executor=use_executor),
        "liquidate_retry_succeeds": _liquidate(P, fail_1002_first, use_executor=use_executor),
        "liquidate_retry_skipped_when_position_gone": _liquidate(P, fail_1002, positions_after=[P[0], P[2]], use_executor=use_executor),
        "liquidate_no_positions": _liquidate([], use_executor=use_executor),
    }


def _current():
    objs = [SimpleNamespace(ticket=2001, symbol="EURUSD", type="BUY", price_open=1.1, profit=7.0),
            SimpleNamespace(ticket=2002, symbol="EURUSD", type="SELL", price_open=1.1, profit=-7.0)]
    return {
        "soft_full": _soft("a", POS),
        "soft_objects": _soft("b", objs),
        "soft_no_modify_method": _soft("c", POS, with_modify=False),
        "soft_empty": _soft("d", []),
        "soft_mt5_fallback_info": _soft_no_connector(POS[:2], SimpleNamespace(point=0.00001, digits=5)),
        "soft_mt5_fallback_none": _soft_no_connector(POS[:2], None),
        "manual_no_broker": _manual(None),
        "manual_get_positions": _manual(_connector(positions=POS)),
        "manual_positions_attr": _manual(_connector(positions_attr={"a": POS[0], "b": POS[2]})),
        "update_equity_red_with_broker": _update_equity_red(_connector(positions=POS[:3])),
        "update_equity_red_no_broker": _update_equity_red(None),
        **_liquidation_scenarios(False),
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


def _norm_logs(rows):
    # đường executor ghi qua logger của L5 (tên khác); so nội dung + cấp độ, bỏ log cảnh báo kích hoạt (do kill switch ghi)
    return [r for r in rows if "SOFT DE-RISKING PROTOCOL ACTIVATED" not in r[1]]


def test_l5_executor_path_matches_golden():
    """Đường live (runner truyền executor của L5) phải cho kết quả/lời gọi/log y hệt đường nội tuyến kế thừa."""
    golden = json.load(open(GOLDEN, encoding="utf-8"))
    objs = [SimpleNamespace(ticket=2001, symbol="EURUSD", type="BUY", price_open=1.1, profit=7.0),
            SimpleNamespace(ticket=2002, symbol="EURUSD", type="SELL", price_open=1.1, profit=-7.0)]
    for key, got in (
        ("soft_full", _soft("a", POS, use_executor=True)),
        ("soft_objects", _soft("b", objs, use_executor=True)),
        ("soft_no_modify_method", _soft("c", POS, use_executor=True, with_modify=False)),
        ("soft_empty", _soft("d", [], use_executor=True)),
    ):
        got = json.loads(json.dumps(got, sort_keys=True, default=str))
        want = golden[key]
        for field in ("result", "locked", "freeze_until", "calls"):
            assert got[field] == want[field], f"{key}.{field}"
        assert _norm_logs(got["logs"]) == _norm_logs(want["logs"]), f"{key}.logs"
    for key, got in (
        ("manual_get_positions", _manual(_connector(positions=POS), use_executor=True)),
        ("manual_positions_attr", _manual(_connector(positions_attr={"a": POS[0], "b": POS[2]}), use_executor=True)),
        ("update_equity_red_with_broker", _update_equity_red(_connector(positions=POS[:3]), use_executor=True)),
    ):
        got = json.loads(json.dumps(got, sort_keys=True, default=str))
        assert got == golden[key], key


def test_liquidation_l5_executor_path_matches_legacy_golden():
    """ADR-003: đường live (executor L5) phải đóng đúng cùng ticket/kết quả như đường nội tuyến; cảnh báo chỉ khi đóng thất bại."""
    golden = json.load(open(GOLDEN, encoding="utf-8"))
    got_all = json.loads(json.dumps(_liquidation_scenarios(True), sort_keys=True, default=str))
    for key, got in got_all.items():
        want = golden[key]
        for field in ("plan", "locked", "freeze_until", "close_calls", "modify_calls"):
            assert got[field] == want[field], f"{key}.{field}"
    assert got_all["liquidate_all_ok_profit_and_loss"]["alerts"] == []
    assert got_all["liquidate_one_fails_others_continue_retry_fails"]["alerts"] == ["EMERGENCY LIQUIDATION: CLOSE FAILED"] * 2
    assert got_all["liquidate_one_raises_others_continue"]["alerts"] == []   # ngoại lệ bị bắt ở L4, không qua nhánh on_failure
    assert got_all["liquidate_retry_succeeds"]["alerts"] == ["EMERGENCY LIQUIDATION: CLOSE FAILED"]
    assert got_all["liquidate_retry_skipped_when_position_gone"]["alerts"] == ["EMERGENCY LIQUIDATION: CLOSE FAILED"]
