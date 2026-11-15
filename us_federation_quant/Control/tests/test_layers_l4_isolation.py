"""Layer isolation cho L4 Rủi ro.

l4_risk.py gộp cả mã kế thừa (kill switch, VaR, warrant, HWM, fleet guard) nên KHÔNG thể cấm mọi import MT5 trong
cả file (kill switch cũ có một import MetaTrader5 lười ở nhánh dự phòng; đây là nợ kế thừa). Cam kết kiểm chứng ở đây:
các hàm ĐÁNH GIÁ của L4 (evaluate_* và hàm giờ phiên) là thuần: không import MT5/mạng, không chạm `mt5`.
"""
import ast
import glob
import os

from us_federation_quant.Anpha.contracts import CloseDirective, MarketView, RiskCheck
from us_federation_quant.Anpha.l4_risk import evaluate_risk

_LAYERS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Anpha")
_FORBIDDEN_ROOTS = {"MetaTrader5", "requests", "urllib", "socket", "http"}
_PURE_NAMES = {"is_us_dst", "get_mt5_server_datetime", "is_friday_or_weekend_curfew",
               "get_last_weekly_open_utc", "is_friday_eod_flat_window"}
_UPSTREAM_LAYERS = ("l1_data", "l2_alpha", "l3_sizing", "l5_execution")


def _pure_functions():
    tree = ast.parse(open(os.path.join(_LAYERS, "l4_risk.py"), encoding="utf-8").read())
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)
            and (n.name.startswith("evaluate_") or n.name in _PURE_NAMES)]


def test_l4_evaluators_are_pure_no_mt5_no_network():
    funcs = _pure_functions()
    assert {f.name for f in funcs} >= {"evaluate_risk", "evaluate_hard_cap", "evaluate_two_tier_exit"}
    for fn in funcs:
        for n in ast.walk(fn):
            if isinstance(n, ast.Import):
                assert all(a.name.split(".")[0] not in _FORBIDDEN_ROOTS for a in n.names), fn.name
            elif isinstance(n, ast.ImportFrom):
                assert (n.module or "").split(".")[0] not in _FORBIDDEN_ROOTS, fn.name
            elif isinstance(n, ast.Name):
                assert n.id != "mt5", f"{fn.name} dùng mt5"


def test_l4_does_not_import_other_upstream_or_execution_layers():
    tree = ast.parse(open(os.path.join(_LAYERS, "l4_risk.py"), encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            assert not any(u in n.module for u in _UPSTREAM_LAYERS), n.module


def test_layers_directory_has_exactly_the_six_layer_files():
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(_LAYERS, "*.py")))
    # Anpha/ (layer) = 6 tầng + contracts.py (hợp đồng dùng chung) + __init__.py
    assert names == ["__init__.py", "contracts.py", "l1_data.py", "l2_alpha.py", "l3_sizing.py", "l4_risk.py",
                     "l5_execution.py", "l6_telemetry.py"], names


def test_contracts_is_the_single_contract_file():
    root = os.path.dirname(_LAYERS)
    found = [p for p in glob.glob(os.path.join(root, "**", "contracts.py"), recursive=True)]
    assert len(found) == 1, found


def test_evaluate_risk_only_emits_directives_and_never_touches_broker():
    def boom(*a, **k):
        raise AssertionError("L4 không được gọi MT5")

    market = MarketView(symbol_info=boom, symbol_tick=boom, resolve_symbol=boom, symbol_spec=boom,
                        is_market_open=boom, trade_mode_full=boom, reopen_state=boom)
    positions = [{"ticket": 7, "symbol": "XAUUSDm", "type": "BUY", "volume": 0.05,
                  "profit": -80.0, "swap": -2.5, "commission": 0.0}]
    res = evaluate_risk(RiskCheck.HARD_CAP_XAUUSD, positions=positions, market=market,
                        params={"max_loss_usd": 75.0})
    assert len(res.directives) == 1 and isinstance(res.directives[0], CloseDirective)
    assert res.directives[0].ticket == 7 and res.directives[0].comment == "XAU HardCap 75"
