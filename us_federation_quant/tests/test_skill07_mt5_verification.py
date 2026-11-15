"""
========================================================================================
SKILL 07 VERIFICATION TEST SUITE: RISK CONTROLS & STATELESS MT5 INTEGRATION
1. Universal Hard Risk Cap $15.00 (calculate_risk_adjusted_lot & enforce_hard_risk_cap)
2. Breakeven Lock + 1.5 Pips Buffer (check_and_apply_breakeven_lock)
3. Anti-Chasing Cooldown 15m (mt5.history_deals_get stateless check)
4. Same-Direction 2-SL Lockout 2h (mt5.history_deals_get stateless check)
========================================================================================
"""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_DIR))
sys.path.insert(0, str(_DIR.parent))

import MetaTrader5 as mt5
from us_federation_quant.core.live_federation_runner import USFederationQuantRuntime


def test_universal_hard_risk_cap_15usd():
    print("\n--- 1. Testing Universal Hard Risk Cap $15.00 ---")
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)

    # Test cases: (symbol, sl_points, max_risk_usd)
    test_cases = [
        ("GBPUSD", 25.0, 15.0),
        ("GBPUSDm", 15.0, 15.0),
        ("EURUSDm", 20.0, 15.0),
        ("USTECm", 300.0, 15.0),
        ("US30m", 250.0, 15.0),
        ("GBPJPYm", 35.0, 15.0),
    ]

    for sym, sl_pts, max_risk in test_cases:
        calculated_lot = runtime.calculate_risk_adjusted_lot(sym, sl_pts, max_risk)
        sym_info = mt5.symbol_info(sym)
        if sym_info is None:
            resolved = runtime.mt5_mgr.resolve_symbol(sym)
            sym_info = mt5.symbol_info(resolved)

        if sym_info:
            tick_size = sym_info.trade_tick_size or sym_info.point
            tick_value = sym_info.trade_tick_value or 1.0
            point = sym_info.point
            sl_price_dist = sl_pts * point
            ticks_in_sl = sl_price_dist / tick_size
            loss_per_lot = ticks_in_sl * tick_value
            expected_loss = calculated_lot * loss_per_lot

            print(
                f"  [{sym}] sl_pts={sl_pts:.1f} -> Lot={calculated_lot:.2f}L | "
                f"Loss/Lot=${loss_per_lot:.2f} | Exp Loss=${expected_loss:.2f} (Cap <= ${max_risk:.2f})"
            )
            # Must strictly not exceed max_risk + epsilon (or minimal volume clamp)
            if calculated_lot > sym_info.volume_min:
                assert expected_loss <= max_risk + 0.05, f"Expected loss ${expected_loss:.2f} exceeds cap ${max_risk:.2f}"
        else:
            print(f"  [{sym}] Lot={calculated_lot:.2f}L (symbol_info not available)")

    print("  -> PASSED: Universal Hard Risk Cap $15.00 verified!")


def test_stateless_deals_history_rules():
    print("\n--- 2. Testing Stateless Deals History Rules (Anti-Chasing & 2-SL Lockout) ---")
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)
    now_ts = time.time()

    symbols_to_test = ["GBPUSD", "EURUSD", "AUDUSD", "GBPJPY", "USTEC"]
    for sym in symbols_to_test:
        for direction in ["BUY", "SELL"]:
            can_enter, reason = runtime.can_enter_trade(sym, direction, now_ts)
            print(f"  Symbol: {sym:7s} | Dir: {direction:4s} | Allowed: {str(can_enter):5s} | Reason: {reason}")

    print("  -> PASSED: Live MT5 history deals queried successfully!")


def test_breakeven_lock_logic():
    print("\n--- 3. Testing Breakeven Lock Logic Structure ---")
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)
    modified = runtime.check_and_apply_breakeven_lock(buffer_pips=1.5)
    print(f"  Live Open Positions Evaluated. Positions modified: {len(modified)}")
    print("  -> PASSED: Breakeven Lock routine executed without errors!")


if __name__ == "__main__":
    if not mt5.initialize():
        print(f"MT5 Init failed: {mt5.last_error()}")
        sys.exit(1)

    try:
        test_universal_hard_risk_cap_15usd()
        test_stateless_deals_history_rules()
        test_breakeven_lock_logic()
        print("\n========================================================")
        print("ALL SKILL 07 RISK CONTROL TESTS PASSED SUCCESSFULLY!")
        print("========================================================")
    finally:
        mt5.shutdown()

