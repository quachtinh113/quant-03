"""Golden test cho đuôi đường vào lệnh (state machine -> open_market_order -> FILLED/REJECTED + revoke warrant).

Đóng băng hành vi trước/sau khi chuyển sang layers/l5_execution.submit_order_intent.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_order_submission.py
ADR-005 thêm 7 kịch bản chốt SL (kịch bản a..j giữ nguyên, không đổi).
Chỉ dùng test double; không gửi lệnh thật. Ghi cả log (cấp độ + nội dung) và thứ tự lời gọi.
"""
import json
import logging
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from us_federation_quant.Document.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "order_submission.json")


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, record):
        self.rows.append([record.levelname, record.getMessage()])


def _run(name, *, action="BUY", exec_result=None, exec_raises=None, create_raises=None, state_id="STATE_01",
         lots=0.07, price=1.1, idm=1.234, policy="EASING", forecast=12.345, sl=1.0950):
    r = RT(initial_capital_usd=9000.0)
    mgr = MagicMock()
    order_state = MagicMock()
    events = []
    order_state.transition_to.side_effect = lambda st, **kw: events.append(["transition", str(getattr(st, "name", st)), kw])
    if create_raises:
        mgr.state_machine.create_order.side_effect = create_raises
    else:
        mgr.state_machine.create_order.side_effect = lambda **kw: (events.append(["create_order", kw]) or order_state)
    if exec_raises:
        mgr.open_market_order.side_effect = exec_raises
    else:
        mgr.open_market_order.side_effect = lambda **kw: (events.append(["open_market_order", kw]) or exec_result)
    r.mt5_mgr = mgr
    warrant = SimpleNamespace(warrant_id="W-123", revoke=MagicMock())
    warrant.revoke.side_effect = lambda **kw: events.append(["revoke", kw])
    pod = SimpleNamespace(state_id=state_id, state_name="State of Test Pod")
    proposal = SimpleNamespace(action=action, carver_forecast=forecast)
    executed = []
    cap = _Capture()
    lg = logging.getLogger("USFederationQuant")
    lg.addHandler(cap)
    old_level = lg.level
    lg.setLevel(logging.DEBUG)
    raised = None
    try:
        with patch("us_federation_quant.Document.live_federation_runner.generate_client_order_id",
                   lambda sid, act: f"CLIENTID-{sid}-{act}-0123456789ABCDEF0123456789"), \
             patch("us_federation_quant.layers.l5_execution.generate_client_order_id",
                   lambda sid, act: f"CLIENTID-{sid}-{act}-0123456789ABCDEF0123456789"):
            try:
                r._submit_proposal_order(pod, proposal, "EURUSDm", lots, sl, 1.1100, 260901, warrant, idm,
                                         policy, price, executed)
            except Exception as e:  # ngoại lệ phải lan ra như cũ (vòng lặp gọi có try/except)
                raised = [type(e).__name__, str(e)]
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old_level)
    return {"events": events, "executed": executed, "logs": cap.rows, "raised": raised,
            "create_called": mgr.state_machine.create_order.called}


def _current():
    ok = {"success": True, "ticket": 555, "price": 1.1002}
    return {
        "success_with_price": _run("a", exec_result=ok),
        "success_default_price": _run("b", exec_result={"success": True, "ticket": 556}),
        "sell_success": _run("c", action="SELL", exec_result=ok),
        "failure_generic": _run("d", exec_result={"success": False, "error": "No money", "retcode": 10019}),
        "failure_market_closed_10018": _run("e", exec_result={"success": False, "error": "Market closed", "retcode": 10018}),
        "failure_no_error_key": _run("f", exec_result={"success": False}),
        "comment_truncation": _run("g", exec_result=ok, state_id="STATE_VERY_LONG_IDENTIFIER_99"),
        "open_raises": _run("h", exec_raises=RuntimeError("ipc down")),
        "create_raises": _run("i", exec_result=ok, create_raises=ValueError("dup id")),
        "no_success_key": _run("j", exec_result={"ticket": 1}),
        # ADR-005: chốt SL cứng — chặn trước create_order, không gọi MT5, thu hồi warrant, không ném ngoại lệ
        "adr5_sl_none_rejected": _run("k", exec_result=ok, sl=None),
        "adr5_sl_zero_rejected": _run("l", exec_result=ok, sl=0),
        "adr5_sl_negative_rejected": _run("m", exec_result=ok, sl=-1.0),
        "adr5_sl_nan_rejected": _run("n", exec_result=ok, sl=float("nan")),
        "adr5_sl_inf_rejected": _run("o", exec_result=ok, sl=float("inf")),
        "adr5_sl_sell_none_rejected": _run("p", action="SELL", exec_result=ok, sl=None),
        "adr5_sl_valid_tiny_passes": _run("q", exec_result=ok, sl=0.00001),
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
