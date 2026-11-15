"""Golden G2 (Bước 5a): điều phối của USFederationQuantRuntime.run() — THỨ TỰ và tham số mọi lời gọi.

Mọi bước (phương thức runner, mt5_mgr, hwm, quad_titans, hub, heartbeat, telemetry...) là test double ghi vào một danh sách sự kiện;
đồng hồ (time.time) tiến theo time.sleep, vòng lặp dừng sau N vòng bằng cách đặt _running=False.
Đóng băng: khởi động, vòng nhanh (3s), vòng chậm (60s), `continue`/sleep(5), lỗi bị nuốt, SystemExit(99), tắt máy.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_run_orchestration.py
Không gửi lệnh thật, không ngủ thật.
"""
import json
import os
from datetime import datetime as _real_dt, timezone
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

import us_federation_quant.core.live_federation_runner as runner_mod
from us_federation_quant.core.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "run_orchestration.json")
RUNNER = "us_federation_quant.core.live_federation_runner"
NOW = _real_dt(2026, 11, 11, 15, 30, tzinfo=timezone.utc)
T0 = 1_800_000_000.0


def _norm(x):
    if isinstance(x, np.ndarray):
        return ["ndarray", list(x.shape)]
    if isinstance(x, _real_dt):
        return x.isoformat()
    if isinstance(x, dict):
        return {str(k): _norm(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    if callable(x) and not isinstance(x, (dict, list, tuple)):
        return "<callable>"
    if isinstance(x, SimpleNamespace):
        return {k: _norm(v) for k, v in vars(x).items()}
    if isinstance(x, Spy):
        return f"<Spy:{x._name}>"
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    return f"<{type(x).__name__}>"


class Spy:
    """Đối tượng ghi lại mọi lời gọi phương thức; `returns` quyết định giá trị trả về theo tên phương thức."""

    def __init__(self, name, events, returns=None, raises=None):
        self._name, self._events, self._returns, self._raises = name, events, returns or {}, raises or {}

    def __getattr__(self, m):
        def f(*a, **k):
            self._events.append([f"{self._name}.{m}", _norm(a), _norm(k)])
            if m in self._raises:
                exc = self._raises[m]
                raise exc() if callable(exc) and isinstance(exc, type) else exc
            v = self._returns.get(m)
            return v(*a, **k) if callable(v) else v
        return f


def _seq(values):
    it = list(values)
    return lambda *a, **k: (it.pop(0) if len(it) > 1 else it[0])


def _run(iters, *, ensure=(True,), account=({"equity": 9_900.0, "balance": 10_000.0},), startup_account=None,
         raises=None, stagnation=False, nuclear=False, sweep=(0.0, 50.0), sweep_raises=False, drawdown=0.012,
         ladder_raises=False, trailing_raises=False, positions=({"ticket": 1},)):
    r = RT(initial_capital_usd=9000.0)
    events = []
    clock = {"t": T0}
    counters = {"ensure": 0}

    def _ensure(*a, **k):
        counters["ensure"] += 1
        events.append(["ensure_mt5_connected", _norm(a), _norm(k)])
        if counters["ensure"] >= iters:
            runner_mod._running = False
        return _seq(ensure)()

    r.ensure_mt5_connected = _ensure
    for name, ret in (("update_symbol_exit_tracking", None), ("enforce_weekend_hold_sweeper", 0),
                      ("enforce_gbpchf_uk100_hard_stop_cap", []), ("enforce_forex_portfolio_hard_stop_cap", []),
                      ("enforce_index_hard_stop_cap", []), ("enforce_xauusd_hard_stop_cap", []),
                      ("manage_multi_tier_profit_ladder", []), ("enforce_two_tier_exit_engine", {}),
                      ("reconcile_index_duplicate_derisking", []), ("scan_and_route_state_proposals", []),
                      ("log_timeline_status", None), ("print_constitutional_dashboard", None)):
        def mk(n, rv):
            def f(*a, **k):
                events.append([n, _norm(a), _norm(k)])
                if raises and raises[0] == n:
                    raise raises[1]
                if n == "manage_multi_tier_profit_ladder" and ladder_raises:
                    raise RuntimeError("ladder boom")
                return rv
            return f
        setattr(r, name, mk(name, ret))

    r.enforce_stagnation_exit = lambda positions, now_utc: (events.append(["enforce_stagnation_exit", _norm(positions), _norm(now_utc)]) or stagnation)
    acc_seq = _seq(account)
    r.mt5_mgr = Spy("mgr", events, returns={
        "get_account_info": lambda *a, **k: acc_seq(), "get_positions": lambda *a, **k: [dict(p) for p in positions]})
    r.hwm = Spy("hwm", events, returns={"update": lambda **k: SimpleNamespace(drawdown_fraction=drawdown)})
    r.quad_titans = Spy("titans", events, returns={"execute_quad_audit": lambda **k: {"nuclear_football_triggered": nuclear}})
    r.ts_manager = Spy("ts", events, raises={"update_trailing_stops": RuntimeError("ts boom")} if trailing_raises else None)
    r.heartbeat = Spy("hb", events, returns={"measure_socket_latency": 12.5})
    r.telemetry = Spy("tel", events)
    hub_pods = {"A": SimpleNamespace(is_active=True), "B": SimpleNamespace(is_active=False), "C": SimpleNamespace(is_active=True)}
    r.hub = SimpleNamespace(states_registry=SimpleNamespace(states=hub_pods),
                            central_risk_desk=SimpleNamespace(kill_switch=Spy("kill", events)))
    if startup_account is not None:
        acc_first = startup_account
    else:
        acc_first = account[0]
    first = {"done": False}
    orig = r.mt5_mgr.get_account_info

    def _get_account(*a, **k):
        events.append(["mgr.get_account_info", [], {}])
        if not first["done"]:
            first["done"] = True
            return acc_first
        return acc_seq()

    r.mt5_mgr.get_account_info = _get_account

    def _sleep(s):
        events.append(["sleep", s])
        clock["t"] += s

    class _FDT(_real_dt):
        @classmethod
        def now(cls, tz=None):
            return NOW

    def _sweep(**k):
        events.append(["vault_sweep", _norm(k)])
        if sweep_raises:
            raise RuntimeError("vault boom")
        return sweep

    runner_mod._running = True
    exit_code = None
    try:
        with patch("time.sleep", side_effect=_sleep), patch("time.time", side_effect=lambda: clock["t"]), \
             patch(f"{RUNNER}.datetime", _FDT), patch("numpy.random.normal", side_effect=lambda *a, **k: np.zeros(a[2])), \
             patch("us_federation_quant.core.institutional_governance_rules.InstitutionalStatutoryRules."
                   "execute_blackrock_profit_sweep", side_effect=_sweep):
            try:
                r.run()
            except SystemExit as e:
                exit_code = e.code
    finally:
        runner_mod._running = True
    return {"events": events, "exit_code": exit_code}


def _current():
    o = {}
    o["two_iterations_slow_then_fast"] = _run(2)
    o["periodic_60s_cycle"] = _run(22)
    o["reconnect_fails_then_ok"] = _run(2, ensure=(False, True))
    o["no_account_info_sleeps_5"] = _run(2, account=(None, {"equity": 9_900.0, "balance": 10_000.0}))
    o["startup_account_none_uses_defaults"] = _run(1, startup_account=None, account=({"equity": 9_900.0, "balance": 10_000.0},))
    o["body_exception_logged_sleep5"] = _run(2, raises=("enforce_gbpchf_uk100_hard_stop_cap", RuntimeError("boom")))
    o["ladder_exception_swallowed"] = _run(1, ladder_raises=True)
    o["trailing_exception_swallowed"] = _run(1, trailing_raises=True)
    o["stagnation_closes_refetches_positions"] = _run(1, stagnation=True)
    o["nuclear_football_exits_99"] = _run(1, nuclear=True, drawdown=0.13)
    o["vault_sweep_positive"] = _run(1, sweep=(250.0, 1250.0))
    o["vault_sweep_raises_swallowed"] = _run(1, sweep_raises=True)
    o["scan_exception_logged_sleep5"] = _run(1, raises=("scan_and_route_state_proposals", RuntimeError("scan boom")))
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
