"""Golden test (đóng băng hành vi) cho 4 hàm enforce_*_hard_stop_cap của runner.

Mục đích: lát chia tầng L5 (tách quyết định thuần sang 05_risk) KHÔNG được đổi hành vi.
Fixture golden được sinh từ mã TRƯỚC khi tách:
    GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_l5_hard_caps.py
Không có MT5 thật: mt5_mgr và telemetry là test double.
"""
import json
import os
from unittest.mock import MagicMock

import pytest

from us_federation_quant.Architecter.live_federation_runner import USFederationQuantRuntime

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "l5_hard_caps.json")

CASES = {
    "enforce_xauusd_hard_stop_cap": 75.0,
    "enforce_index_hard_stop_cap": 60.0,
    "enforce_gbpchf_uk100_hard_stop_cap": 15.0,
    "enforce_forex_portfolio_hard_stop_cap": 15.0,
}


def _p(ticket, symbol, profit, swap=0.0, commission=0.0, **extra):
    d = {"ticket": ticket, "symbol": symbol, "type": "BUY", "volume": 0.1,
         "profit": profit, "swap": swap, "commission": commission}
    d.update(extra)
    return d


def _positions():
    return [
        _p(1, "XAUUSDm", -75.0),            # đúng ngưỡng vàng
        _p(2, "XAUUSDm", -74.99),           # sát ngưỡng, không đóng
        _p(3, "XAUUSDm", -70.0, swap=-3.0, commission=-2.5),  # swap+comm kéo qua ngưỡng
        _p(4, "GOLD", -90.0),               # tên GOLD
        _p(5, "USTECm", -60.0),             # đúng ngưỡng index
        _p(6, "US30m", -59.0),              # chưa tới
        _p(7, "US500", -100.0),             # index lỗ nặng
        _p(8, "NAS100", -61.0),
        _p(9, "GBPCHFm", -15.0),            # đúng ngưỡng 15
        _p(10, "UK100m", -20.0),
        _p(11, "EURUSDm", -15.01),
        _p(12, "EURUSDm", -14.99),
        _p(13, "USDJPYm", -30.0, close_fail=True),   # đóng thất bại
        _p(14, "HK50m", -500.0),            # bị loại khỏi forex portfolio
        _p(15, "XAUUSD", -500.0),           # bị loại khỏi forex portfolio
        _p(16, "EURUSDm", 10.0),            # lãi
        {"ticket": 17, "symbol": "GBPUSDm", "type": "SELL", "volume": 0.2, "profit": -16.0},  # thiếu swap/commission
    ]


def _run(method_name, cap):
    runner = USFederationQuantRuntime(initial_capital_usd=9000.0)
    runner.mt5_mgr = MagicMock()
    runner.telemetry = MagicMock()
    positions = _positions()
    fail = {p["ticket"] for p in positions if p.get("close_fail")}
    runner.mt5_mgr.get_positions.return_value = [
        {k: v for k, v in p.items() if k != "close_fail"} for p in positions
    ]
    runner.mt5_mgr.close_position.side_effect = (
        lambda ticket, comment: {"success": ticket not in fail, "ticket": ticket}
    )
    returned = getattr(runner, method_name)(max_loss_usd=cap)
    return {
        "returned": returned,
        "close_calls": [[c.kwargs.get("ticket"), c.kwargs.get("comment")]
                        for c in runner.mt5_mgr.close_position.call_args_list],
        "alerts": [[c.kwargs.get("subject"), c.kwargs.get("body")]
                   for c in runner.telemetry.broadcast_critical_alert.call_args_list],
    }


def _current():
    return {name: _run(name, cap) for name, cap in CASES.items()}


def test_generate_or_match_golden():
    current = _current()
    if os.environ.get("GENERATE_GOLDEN") == "1":
        os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
        with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False, sort_keys=True)
        pytest.skip("golden đã được sinh")
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)
    assert json.loads(json.dumps(current, sort_keys=True)) == golden
