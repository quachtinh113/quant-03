"""Golden test (Phần 2, Bước 4): vòng đời kết nối ensure_mt5_connected (retry, mt5.shutdown thô, sleep, log).

Ghi THỨ TỰ sự kiện: ensure_connected / shutdown / sleep(giây) / connect, log, giá trị trả về.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_reconnect.py
Chỉ dùng test double; không gửi lệnh thật, không ngủ thật.
"""
import json
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from us_federation_quant.core.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "reconnect.json")
RUNNER = "us_federation_quant.core.live_federation_runner"


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, r):
        self.rows.append([r.levelname, r.getMessage()])


def _run(ensure=(False,), connect=(), shutdown_raises=False, running=True, **kw):
    r = RT(initial_capital_usd=9000.0)
    events = []
    ens, con = list(ensure), list(connect)
    mgr = MagicMock()

    def _ens():
        events.append("ensure_connected")
        return ens.pop(0) if ens else False

    def _con():
        events.append("connect")
        v = con.pop(0) if con else False
        if isinstance(v, Exception):
            raise v
        return v

    mgr.ensure_connected.side_effect = _ens
    mgr.connect.side_effect = _con
    r.mt5_mgr = mgr

    def _shutdown():
        events.append("shutdown")
        if shutdown_raises:
            raise RuntimeError("shutdown boom")

    cap = _Cap()
    lg = logging.getLogger("USFederationQuant")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    try:
        with patch("time.sleep", side_effect=lambda s: events.append(["sleep", s])), \
             patch("MetaTrader5.shutdown", side_effect=_shutdown), \
             patch(f"{RUNNER}._running", running):
            res = r.ensure_mt5_connected(**kw)
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)
    return {"result": res, "events": events, "logs": cap.rows}


def _current():
    return {
        "already_connected": _run(ensure=(True,)),
        "reconnect_first_try": _run(connect=(True,), max_retries=5, delay=15.0),
        "reconnect_third_try": _run(connect=(False, False, True), max_retries=5, delay=15.0),
        "exhausted_returns_false": _run(connect=(False, False, False), max_retries=3, delay=15.0),
        "connect_raises_each_time": _run(connect=(RuntimeError("a"), RuntimeError("b")), max_retries=2, delay=1.0),
        "connect_raises_then_ok": _run(connect=(RuntimeError("a"), True), max_retries=5, delay=2.0),
        "shutdown_raises_swallowed": _run(connect=(True,), shutdown_raises=True, max_retries=3, delay=3.0),
        "running_false_skips_loop": _run(connect=(True,), running=False, max_retries=3, delay=15.0),
        "custom_delay_and_default_args": _run(connect=(False, True), delay=5.0),
        "max_retries_zero": _run(connect=(True,), max_retries=0),
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
