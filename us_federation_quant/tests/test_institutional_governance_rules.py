"""
Unit tests for the 4 Judicial Orders (US Federation Quant).
1. LỆNH 1: Roll-Over Curfew (04:45 - 05:15 sáng VN / 21:45 - 22:15 UTC).
2. LỆNH 2: Slippage Cap (Max 1.5 pips / Ping > 150ms).
3. LỆNH 3: Farhi Disaster Jump Filter (Hạ 60% lot nếu dispersion > 3 sigma).
4. LỆNH 4: BlackRock Profit Sweep (Tự động quét 50% lãi ròng vào ví lạnh Hamilton).
"""

import sys
from datetime import datetime, time as dtime, timezone
from pathlib import Path
import pytest

_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE = _DIR
for p in [str(_DIR), str(_DIR / "us_federation_quant"), str(_DIR / "All_Fleet_Bot")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from us_federation_quant.institutional_governance_rules import InstitutionalStatutoryRules, HamiltonColdVaultManager


def test_lenh_01_rollover_curfew():
    # Outside curfew (e.g. 14:00 UTC = 21:00 VN) -> Compliant
    dt_normal = datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)
    res_normal = InstitutionalStatutoryRules.check_rollover_curfew(dt_normal)
    assert res_normal.is_compliant is True

    # Inside curfew (22:00 UTC = 05:00 sáng VN, within 04:45 - 05:15 VN) -> Rejected
    dt_curfew = datetime(2026, 9, 21, 22, 0, tzinfo=timezone.utc)
    res_curfew = InstitutionalStatutoryRules.check_rollover_curfew(dt_curfew)
    assert res_curfew.is_compliant is False
    assert res_curfew.rejection_reason == "ROLLOVER_CURFEW_FROZEN"


def test_lenh_02_slippage_and_latency():
    # Normal ping (65ms) & slippage (2.0 pts = 0.2 pips) -> Compliant
    res_ok = InstitutionalStatutoryRules.check_execution_latency_and_slippage(socket_latency_ms=65.0, slippage_points=2.0)
    assert res_ok.is_compliant is True

    # High ping (>150ms) -> Rejected
    res_lag = InstitutionalStatutoryRules.check_execution_latency_and_slippage(socket_latency_ms=185.0, slippage_points=2.0)
    assert res_lag.is_compliant is False
    assert res_lag.rejection_reason == "EXCESSIVE_LATENCY_REJECT"

    # Excessive slippage (>15 pts = 1.5 pips) -> Rejected
    res_slip = InstitutionalStatutoryRules.check_execution_latency_and_slippage(socket_latency_ms=50.0, slippage_points=22.0)
    assert res_slip.is_compliant is False
    assert res_slip.rejection_reason == "EXCESSIVE_SLIPPAGE_REJECT"


def test_lenh_03_farhi_disaster_jump_filter():
    # Carry asset with dispersion <= 3.0 sigma -> No haircut
    lots_normal, trig_norm, _ = InstitutionalStatutoryRules.apply_farhi_disaster_jump_filter(
        target_asset="USDJPYm",
        authorized_lots=1.0,
        yield_dispersion_sigma=1.8
    )
    assert trig_norm is False
    assert lots_normal == 1.0

    # Carry asset with dispersion > 3.0 sigma -> Hạ 60% lot (còn 40%)
    lots_haircut, trig_shock, msg = InstitutionalStatutoryRules.apply_farhi_disaster_jump_filter(
        target_asset="USDJPYm",
        authorized_lots=1.0,
        yield_dispersion_sigma=3.8
    )
    assert trig_shock is True
    assert lots_haircut == 0.40
    assert "FARHI DISASTER JUMP SHIELD" in msg


def test_lenh_04_blackrock_profit_sweep(tmp_path):
    # Vault sweeps 50% of new profits beyond High-Water-Mark
    ledger_file = tmp_path / "test_hamilton_vault.json"
    vault = HamiltonColdVaultManager(ledger_path=ledger_file)
    vault.high_water_mark = 10_000.0
    vault.cumulative_reserve = 1_000.0

    # Profit of $500 -> 50% ($250) swept into reserve
    swept, total_res = vault.execute_50_pct_profit_sweep(current_equity=10_500.0)
    assert swept == 250.0
    assert total_res == 1_250.0
    assert vault.high_water_mark == 10_500.0

    # If equity drops or stays same -> No sweep
    swept_zero, total_res_same = vault.execute_50_pct_profit_sweep(current_equity=10_300.0)
    assert swept_zero == 0.0
    assert total_res_same == 1_250.0


def test_pre_order_routing_statutory_gate_all_orders():
    # Normal compliant order with Farhi check
    approved, final_lots, checks = InstitutionalStatutoryRules.audit_pre_order_routing(
        target_asset="EURUSDm",
        requested_lots=0.10,
        current_inventory_lots=0.0,
        total_active_equity=10_000.0,
        socket_latency_ms=50.0,
        slippage_points=1.0,
        yield_dispersion_sigma=0.5,
        now_utc=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert approved is True
    assert final_lots == 0.10

    # Order during Roll-Over Curfew (04:45 - 05:15 VN / 22:00 UTC) -> Rejected
    approved_curfew, _, checks_curfew = InstitutionalStatutoryRules.audit_pre_order_routing(
        target_asset="EURUSDm",
        requested_lots=0.10,
        current_inventory_lots=0.0,
        total_active_equity=10_000.0,
        socket_latency_ms=50.0,
        slippage_points=1.0,
        now_utc=datetime(2026, 9, 21, 22, 0, tzinfo=timezone.utc),
    )
    assert approved_curfew is False


def test_tang_05_correlation_spike_circuit_breaker():
    # Normal correlation (<= 10 pairs) -> Compliant
    res_normal = InstitutionalStatutoryRules.check_correlation_spike_circuit_breaker(mock_high_pairs_count=4)
    assert res_normal.is_compliant is True

    # Correlation Spike (> 10 pairs) -> Non-compliant, triggers de-leverage
    res_spike = InstitutionalStatutoryRules.check_correlation_spike_circuit_breaker(mock_high_pairs_count=18)
    assert res_spike.is_compliant is False
    assert res_spike.rejection_reason == "CORRELATION_SPIKE_DELEVERAGE_50"

    # Pre-order routing with correlation spike throttles lot size by 50%
    approved, final_lots, checks = InstitutionalStatutoryRules.audit_pre_order_routing(
        target_asset="EURUSDm",
        requested_lots=0.20,
        current_inventory_lots=0.0,
        total_active_equity=10_000.0,
        mock_high_correlation_pairs=18,
        now_utc=datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc),
    )
    assert approved is True
    assert final_lots == 0.10  # 0.20 cut in half to 0.10!


def test_tang_06_macro_news_blackout():
    # Outside news embargo window (e.g. Friday 10:00 UTC, NFP is 12:30 UTC) -> Compliant
    dt_calm = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
    res_calm = InstitutionalStatutoryRules.check_macro_news_blackout(dt_calm)
    assert res_calm.is_compliant is True

    # Inside NFP news blackout window (Friday 12:25 UTC, 5 mins before NFP) -> Frozen
    dt_nfp_embargo = datetime(2026, 9, 25, 12, 25, tzinfo=timezone.utc)
    res_nfp = InstitutionalStatutoryRules.check_macro_news_blackout(dt_nfp_embargo)
    assert res_nfp.is_compliant is False
    assert res_nfp.rejection_reason == "MACRO_NEWS_BLACKOUT_FROZEN"

    # Pre-order routing during NFP is rejected
    approved_nfp, _, checks_nfp = InstitutionalStatutoryRules.audit_pre_order_routing(
        target_asset="EURUSDm",
        requested_lots=0.10,
        current_inventory_lots=0.0,
        total_active_equity=10_000.0,
        now_utc=dt_nfp_embargo,
    )
    assert approved_nfp is False

