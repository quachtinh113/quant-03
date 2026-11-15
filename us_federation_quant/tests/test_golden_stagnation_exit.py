"""Golden test cho Stagnation Exit (8h) — đóng băng hành vi trước/sau khi chuyển quyết định sang L4 và thực thi sang L5.

Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_stagnation_exit.py
Chỉ dùng test double; không gửi lệnh thật.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from us_federation_quant.core.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "stagnation_exit.json")
UTC = timezone.utc
NOW = datetime(2026, 11, 11, 14, 0, tzinfo=UTC)


def _pos(ticket, symbol="EURUSDm", age_h=9.0, profit=-3.0, swap=0.0, time_kind="dt"):
    opened = NOW - timedelta(hours=age_h)
    t = {"dt": opened, "naive": opened.replace(tzinfo=None), "epoch": opened.timestamp(),
         "none": None, "str": "2026-11-11", "missing": None}[time_kind]
    p = {"ticket": ticket, "symbol": symbol, "profit": profit, "swap": swap}
    if time_kind != "missing":
        p["time"] = t
    return p


def _scenario(name, positions, ladder=(), tier2=(), market_open=None, close_fail=()):
    r = RT(initial_capital_usd=9000.0)
    mgr = MagicMock()
    mgr.is_market_open.side_effect = lambda s: True if market_open is None else bool(market_open.get(s, True))
    mgr.close_position.side_effect = lambda **kw: {"success": kw["ticket"] not in close_fail, "ticket": kw["ticket"]}
    r.mt5_mgr = mgr
    r._profit_ladder_locked_tickets = set(ladder)
    r._tier2_locked_tickets = set(tier2)
    flag = r.enforce_stagnation_exit([dict(p) for p in positions], NOW)
    return {
        "flag": flag,
        "close_calls": [dict(c.kwargs) for c in mgr.close_position.call_args_list],
        "market_checked": [c.args[0] for c in mgr.is_market_open.call_args_list],
        "ladder_after": sorted(r._profit_ladder_locked_tickets),
        "tier2_after": sorted(r._tier2_locked_tickets),
    }


def _current():
    out = {}
    out["basic_cut"] = _scenario("basic", [_pos(1)])
    out["profit_immunity"] = _scenario("pi", [_pos(2, profit=0.5), _pos(3, profit=0.01)])
    out["ladder_locked_skip"] = _scenario("ll", [_pos(4)], ladder={4})
    out["tier2_locked_skip"] = _scenario("t2", [_pos(5)], tier2={5})
    out["age_below_8h"] = _scenario("a", [_pos(6, age_h=7.99)])
    out["age_exactly_8h"] = _scenario("a8", [_pos(7, age_h=8.0)])
    out["pnl_boundaries"] = _scenario("pb", [_pos(8, profit=-6.0), _pos(9, profit=-6.01), _pos(10, profit=0.0)])
    out["swap_counts"] = _scenario("sw", [_pos(11, profit=-5.0, swap=-2.0), _pos(12, profit=-7.0, swap=2.0)])
    out["market_closed"] = _scenario("mc", [_pos(13, "XAUUSDm"), _pos(14, "EURUSDm")], market_open={"XAUUSDm": False})
    out["time_formats"] = _scenario("tf", [_pos(15, time_kind="naive"), _pos(16, time_kind="epoch"),
                                           _pos(17, time_kind="none"), _pos(18, time_kind="str"),
                                           _pos(19, time_kind="missing")])
    out["close_fails_still_flags"] = _scenario("cf", [_pos(20), _pos(21)], close_fail={20})
    out["prune_stale_locks"] = _scenario("pr", [_pos(22, profit=1.0)], ladder={22, 999}, tier2={22, 888})
    out["empty"] = _scenario("e", [])
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
