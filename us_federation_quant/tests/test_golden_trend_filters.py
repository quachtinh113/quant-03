"""Golden test 4b: chuỗi đọc nến (copy_rates_from_pos -> mgr.get_rates) + quyết định EMA200 của hai bộ lọc xu hướng.

Đóng băng: kết quả allow/deny, THỨ TỰ và tham số các lần đọc nến, log.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_trend_filters.py
Chỉ dùng test double; không gửi lệnh thật.
"""
import json
import logging
import os
from unittest.mock import MagicMock, patch

import MetaTrader5 as _mt5
import numpy as np
import pandas as pd
import pytest

from us_federation_quant.core.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "trend_filters.json")
_TF = {getattr(_mt5, n): n.replace("TIMEFRAME_", "") for n in dir(_mt5) if n.startswith("TIMEFRAME_")}


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, r):
        self.rows.append([r.levelname, r.getMessage()])


def bars(n, lo=100.0, hi=110.0, kind="df"):
    closes = np.linspace(lo, hi, n)
    if kind == "df":
        return pd.DataFrame({"close": closes})
    arr = np.zeros(n, dtype=[("close", "f8")])
    arr["close"] = closes
    return arr


def _run(fn, args, copy_results, mgr_results=None, copy_raises=None):
    r = RT(initial_capital_usd=9000.0)
    mgr = MagicMock()
    mgr.resolve_symbol.side_effect = lambda s: s + "m" if not s.endswith("m") else s
    seq = list(mgr_results or [])
    mgr.get_rates.side_effect = lambda *a, **k: (seq.pop(0) if seq else None)
    r.mt5_mgr = mgr
    calls, copies = [], list(copy_results)

    def fake_copy(sym, tf, start, count):
        calls.append([sym, _TF.get(tf, str(tf)), start, count])
        if copy_raises:
            raise copy_raises
        return copies.pop(0) if copies else None

    cap = _Cap()
    lg = logging.getLogger("USFederationQuant")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    try:
        with patch("MetaTrader5.copy_rates_from_pos", side_effect=fake_copy):
            res = getattr(r, fn)(*args)
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)
    return {"allow": res, "copy_calls": calls,
            "get_rates_calls": [[list(c.args), dict(c.kwargs)] for c in mgr.get_rates.call_args_list],
            "resolve_calls": [c.args[0] for c in mgr.resolve_symbol.call_args_list], "logs": cap.rows}


def _current():
    E, J = "check_eurgbp_d1_ema200_filter", "check_jpy_macro_trend_filter"
    o = {}
    # ---- EURGBP D1 EMA200 (giá lên: EMA ~ 107)
    o["eg_buy_above_ema"] = _run(E, ("EURGBPm", 109.0, "BUY"), [bars(200)])
    o["eg_buy_below_ema_denied"] = _run(E, ("EURGBPm", 100.5, "BUY"), [bars(200)])
    o["eg_sell_always_allowed"] = _run(E, ("EURGBPm", 100.5, "SELL"), [bars(200)])
    o["eg_ndarray_rates"] = _run(E, ("EURGBPm", 100.5, "BUY"), [bars(200, kind="np")])
    o["eg_retry_literal_symbol"] = _run(E, ("EURGBPm", 109.0, "BUY"), [bars(150), bars(200)])
    o["eg_mgr_fallback_ok"] = _run(E, ("EURGBPm", 100.5, "BUY"), [bars(150), bars(120)], mgr_results=[bars(200)])
    o["eg_mgr_fallback_short_keeps_trade"] = _run(E, ("EURGBPm", 100.5, "BUY"), [None, None], mgr_results=[bars(100)])
    o["eg_mgr_returns_none"] = _run(E, ("EURGBPm", 100.5, "BUY"), [None, None], mgr_results=[None])
    o["eg_not_eurgbp_no_calls"] = _run(E, ("EURUSDm", 1.0, "BUY"), [])
    o["eg_exception_keeps_trade"] = _run(E, ("EURGBPm", 100.5, "BUY"), [], copy_raises=RuntimeError("ipc"))
    # ---- JPY macro trend (H4 -> D1 -> mgr H4)
    o["jp_buy_below_ema_denied"] = _run(J, ("USDJPYm", 100.5, "BUY"), [bars(200)])
    o["jp_sell_above_ema_denied"] = _run(J, ("USDJPYm", 111.0, "SELL"), [bars(200)])
    o["jp_buy_above_ok"] = _run(J, ("USDJPYm", 111.0, "BUY"), [bars(200)])
    o["jp_sell_below_ok"] = _run(J, ("USDJPYm", 100.5, "SELL"), [bars(200)])
    o["jp_h4_short_falls_to_d1"] = _run(J, ("USDJPYm", 100.5, "BUY"), [bars(40), bars(120)])
    o["jp_span_shrinks_short_df"] = _run(J, ("GBPJPYm", 100.5, "BUY"), [bars(60)])
    o["jp_mgr_h4_fallback"] = _run(J, ("EURJPYm", 100.5, "BUY"), [bars(20), bars(25)], mgr_results=[bars(35)])
    o["jp_mgr_too_short_keeps_trade"] = _run(J, ("EURJPYm", 100.5, "BUY"), [None, None], mgr_results=[bars(10)])
    o["jp_not_jpy_no_calls"] = _run(J, ("EURUSDm", 1.0, "BUY"), [])
    o["jp_exception_keeps_trade"] = _run(J, ("USDJPYm", 100.5, "BUY"), [], copy_raises=RuntimeError("ipc"))
    o["jp_ndarray_rates"] = _run(J, ("USDJPYm", 100.5, "BUY"), [bars(200, kind="np")])
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
