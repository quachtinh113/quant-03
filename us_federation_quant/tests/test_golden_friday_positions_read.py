"""Golden test (Phần 1, Bước 4): nguồn đọc vị thế của enforce_friday_eod_flat (mt5.positions_get -> dự phòng mgr.get_positions).

Bổ sung cho nhóm friday_eod của test_golden_l4_exits.py: ghi số lần gọi mgr.get_positions, lệnh đóng, log, giá trị trả về.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_friday_positions_read.py
Chỉ dùng test double; không gửi lệnh thật.
"""
import json
import logging
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from us_federation_quant.Document.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "friday_positions_read.json")


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, r):
        self.rows.append([r.levelname, r.getMessage()])


def _run(mt5_positions=None, mt5_raises=None, mgr_positions=None, now_utc=None, close_fail=()):
    r = RT(initial_capital_usd=9000.0)
    mgr = MagicMock()
    mgr.get_positions.return_value = mgr_positions
    mgr.close_position.side_effect = lambda ticket=None, **kw: {"success": ticket not in close_fail, "ticket": ticket, "error": "x"}
    r.mt5_mgr = mgr
    cap = _Cap()
    lg = logging.getLogger("USFederationQuant")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    try:
        side = mt5_raises if mt5_raises else None
        with patch("MetaTrader5.positions_get", side_effect=side, return_value=mt5_positions) as pg:
            res = r.enforce_friday_eod_flat(now_utc)
            pg_calls = pg.call_count
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)
    return {"result": res, "positions_get_calls": pg_calls, "mgr_get_positions_calls": mgr.get_positions.call_count,
            "closed": [dict(c.kwargs) for c in mgr.close_position.call_args_list], "logs": cap.rows}


def _dict_pos(t, sym="EURUSDm"):
    return {"ticket": t, "symbol": sym, "profit": 1.0}


def _current():
    fri = datetime(2026, 11, 6, 21, 45, tzinfo=timezone.utc)
    objs = [SimpleNamespace(ticket=11, symbol="EURUSDm", profit=1.5), SimpleNamespace(ticket=12, symbol="UK100m", profit=-2.0)]
    return {
        "mt5_nonempty_skips_mgr": _run(mt5_positions=objs, mgr_positions=[_dict_pos(99)]),
        "mt5_none_mgr_used": _run(mt5_positions=None, mgr_positions=[_dict_pos(1), _dict_pos(2, "XAUUSDm")]),
        "mt5_empty_list_mgr_used": _run(mt5_positions=[], mgr_positions=[_dict_pos(3)]),
        "both_empty_returns_zero": _run(mt5_positions=None, mgr_positions=[]),
        "both_none_returns_zero": _run(mt5_positions=None, mgr_positions=None),
        "mt5_raises_logged_returns_zero": _run(mt5_raises=RuntimeError("ipc down"), mgr_positions=[_dict_pos(4)]),
        "mt5_objects_with_now_tiering": _run(mt5_positions=objs, now_utc=datetime(2026, 11, 6, 20, 20, tzinfo=timezone.utc)),
        "mgr_positions_close_fail_counts": _run(mt5_positions=None, mgr_positions=[_dict_pos(5), _dict_pos(6)], close_fail={5}),
        "friday_2145_all": _run(mt5_positions=objs, now_utc=fri),
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
