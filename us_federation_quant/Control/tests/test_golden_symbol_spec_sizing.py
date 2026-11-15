"""Golden test 4a: đọc spec symbol (symbol_info + chuỗi dự phòng) và hai hàm sizing dùng nó.

Đóng băng: kết quả lot, THỨ TỰ các lần gọi MetaTrader5.symbol_info, lời gọi mgr (resolve_symbol/get_symbol_spec), log.
Sinh fixture từ mã TRƯỚC khi chuyển đọc dữ liệu sang L1:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_symbol_spec_sizing.py
Chỉ dùng test double; không gửi lệnh thật.
"""
import json
import logging
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from us_federation_quant.Architecter.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "symbol_spec_sizing.json")


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, r):
        self.rows.append([r.levelname, r.getMessage()])


def info(**kw):
    d = dict(trade_tick_size=0.00001, trade_tick_value=1.0, point=0.00001, volume_min=0.01, volume_max=100.0,
             volume_step=0.01)
    d.update(kw)
    return SimpleNamespace(**d)


def _run(fn_name, args, table, resolve=None, mgr_spec=None, attrs=None, no_mgr=False):
    r = RT(initial_capital_usd=9000.0)
    mgr = MagicMock()
    mgr.resolve_symbol.side_effect = lambda s: (resolve or {}).get(s, s)
    mgr.get_symbol_spec.return_value = mgr_spec
    if no_mgr:
        del r.mt5_mgr
    else:
        r.mt5_mgr = mgr
    for k, v in (attrs or {}).items():
        setattr(r, k, v)
    calls = []
    cap = _Cap()
    lg = logging.getLogger("USFederationQuant")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    raised = None
    out = None
    try:
        with patch("MetaTrader5.symbol_info", side_effect=lambda s: (calls.append(s) or table.get(s))):
            try:
                out = getattr(r, fn_name)(*args)
            except Exception as e:
                raised = [type(e).__name__, str(e)]
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)
    return {"result": out, "raised": raised, "symbol_info_calls": calls,
            "resolve_calls": [c.args[0] for c in mgr.resolve_symbol.call_args_list] if not no_mgr else None,
            "spec_calls": [c.args[0] for c in mgr.get_symbol_spec.call_args_list] if not no_mgr else None,
            "logs": cap.rows}


def _current():
    out = {}
    E = info()
    # ---- enforce_hard_risk_cap(symbol, raw_lot, sl_distance_price, max_risk_usd)
    hc = "enforce_hard_risk_cap"
    out["hc_normal"] = _run(hc, ("EURUSDm", 0.50, 0.0050, 15.0), {"EURUSDm": E})
    out["hc_index_cap60"] = _run(hc, ("USTECm", 2.0, 5.0, 100.0), {"USTECm": info(trade_tick_size=0.01, trade_tick_value=0.01)})
    out["hc_sl_zero_returns_vol_min"] = _run(hc, ("EURUSDm", 0.5, 0.0, 15.0), {"EURUSDm": info(volume_min=0.02)})
    out["hc_no_info_after_resolve"] = _run(hc, ("XYZ", 0.5, 0.01, 15.0), {}, resolve={"XYZ": "XYZm"})
    out["hc_resolve_path"] = _run(hc, ("EURUSD", 0.5, 0.0050, 15.0), {"EURUSDm": E}, resolve={"EURUSD": "EURUSDm"})
    out["hc_tick_size_zero_uses_point"] = _run(hc, ("EURUSDm", 0.5, 0.0050, 15.0), {"EURUSDm": info(trade_tick_size=0.0, point=0.0001)})
    out["hc_tick_value_zero_uses_one"] = _run(hc, ("EURUSDm", 0.5, 0.0050, 15.0), {"EURUSDm": info(trade_tick_value=0.0)})
    out["hc_step_0p1_and_vmax"] = _run(hc, ("EURUSDm", 80.0, 0.0001, 15.0), {"EURUSDm": info(volume_step=0.1, volume_max=5.0)})
    out["hc_class_override"] = _run(hc, ("EURUSDm", 5.0, 0.0050, 50.0), {"EURUSDm": E}, attrs={"MAX_HARD_RISK_USD": 5.0})
    out["hc_no_mgr_attr"] = _run(hc, ("EURUSD", 0.5, 0.0050, 15.0), {}, no_mgr=True)
    # ---- calculate_risk_adjusted_lot(symbol, sl_points, max_risk_usd)
    cl = "calculate_risk_adjusted_lot"
    out["cl_direct"] = _run(cl, ("EURUSDm", 300.0, 15.0), {"EURUSDm": E})
    out["cl_via_resolve"] = _run(cl, ("EURUSD", 300.0, 15.0), {"EURUSDm": E}, resolve={"EURUSD": "EURUSDm"})
    out["cl_via_plus_m"] = _run(cl, ("EURUSD", 300.0, 15.0), {"EURUSDm": E})
    out["cl_via_strip_m"] = _run(cl, ("EURUSDm", 300.0, 15.0), {"EURUSD": E})
    out["cl_index_clip"] = _run(cl, ("USTECm", 50.0, 15.0), {"USTECm": info(trade_tick_size=0.01, trade_tick_value=0.01, point=0.01)})
    out["cl_min_vol_clamp_reduces_step"] = _run(cl, ("EURUSDm", 10.0, 1.0), {"EURUSDm": info(volume_min=0.5, volume_step=0.1)})
    out["cl_sl_points_floor_10"] = _run(cl, ("EURUSDm", 2.0, 15.0), {"EURUSDm": E})
    out["cl_tick_size_zero"] = _run(cl, ("EURUSDm", 300.0, 15.0), {"EURUSDm": info(trade_tick_size=0.0)})
    out["cl_point_zero"] = _run(cl, ("EURUSDm", 300.0, 15.0), {"EURUSDm": info(point=0.0)})
    out["cl_mgr_spec_fallback"] = _run(cl, ("NOPE", 300.0, 15.0), {}, mgr_spec={"point": 0.001, "tick_size": 0.001, "tick_value": 2.0, "volume_min": 0.02, "volume_max": 50.0, "volume_step": 0.02})
    out["cl_mgr_spec_defaults"] = _run(cl, ("NOPE", 300.0, 15.0), {}, mgr_spec={})
    out["cl_no_mgr_attr_raises"] = _run(cl, ("NOPE", 300.0, 15.0), {}, no_mgr=True)
    out["cl_max_risk_over_universal"] = _run(cl, ("EURUSDm", 300.0, 99.0), {"EURUSDm": E})
    return out


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
