"""
========================================================================================
US FEDERATION QUANT — UNIT TESTS FOR SUPREME COURT AUTO-QUARANTINE & CIRCUIT BREAKER
Module: tests/test_supreme_court_circuit_breaker.py
========================================================================================
"""

from datetime import datetime, time as dtime, timezone
from pathlib import Path
import pytest
import sys

_DIR = Path(__file__).resolve().parent.parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

import importlib
_sc_manager_mod = importlib.import_module("us_federation_quant.02_supreme_court.supreme_court_circuit_breaker_manager")
SupremeCourtCircuitBreakerManager = _sc_manager_mod.SupremeCourtCircuitBreakerManager
PodQuarantineRecord = _sc_manager_mod.PodQuarantineRecord
SystemCircuitBreakerSnapshot = _sc_manager_mod.SystemCircuitBreakerSnapshot

from us_federation_quant.institutional_governance_rules import InstitutionalStatutoryRules


def test_pod_quarantine_ladder():
    manager = SupremeCourtCircuitBreakerManager()

    # Normal pod (DD = 1.0%)
    rec1 = manager.audit_and_enforce_state_pod(
        state_id="STATE_01",
        state_name="Gold Scalp",
        primary_asset="XAUUSDm",
        allocated_capital=500.0,
        current_equity=495.0,
        peak_equity=500.0,
    )
    assert rec1.quarantine_status == "NORMAL"
    assert rec1.circuit_breaker_active is False

    # De-leveraged pod (DD = 3.5%)
    rec2 = manager.audit_and_enforce_state_pod(
        state_id="STATE_22",
        state_name="GBPUSD Flow",
        primary_asset="GBPUSDm",
        allocated_capital=500.0,
        current_equity=482.5,
        peak_equity=500.0,
    )
    assert rec2.quarantine_status == "DELEVERAGED_50"
    assert rec2.circuit_breaker_active is False

    # Quarantined pod (DD = 6.0%)
    rec3 = manager.audit_and_enforce_state_pod(
        state_id="STATE_05",
        state_name="BTC Volatility",
        primary_asset="BTCUSDm",
        allocated_capital=100.0,
        current_equity=94.0,
        peak_equity=100.0,
    )
    assert rec3.quarantine_status == "QUARANTINED"
    assert rec3.circuit_breaker_active is True


def test_order_routing_authorization():
    manager = SupremeCourtCircuitBreakerManager()

    # Setup 1 normal pod and 1 quarantined pod
    manager.audit_and_enforce_state_pod("STATE_01", "Gold", "XAUUSDm", 500.0, 500.0, 500.0)
    manager.audit_and_enforce_state_pod("STATE_05", "BTC", "BTCUSDm", 100.0, 93.0, 100.0)
    manager.audit_and_enforce_state_pod("STATE_22", "GBPUSD", "GBPUSDm", 500.0, 482.5, 500.0)

    # Test outside curfew, normal latency (non-curfew time: 10:00 UTC)
    normal_utc = datetime(2026, 9, 28, 10, 0, 0, tzinfo=timezone.utc)

    # Normal state should be approved
    ok1, lots1, msg1 = manager.authorize_order_routing(
        "STATE_01", "XAUUSDm", 0.10, 10_000.0, 500.0, 500.0, socket_latency_ms=45.0, slippage_points=1.0, now_utc=normal_utc
    )
    assert ok1 is True
    assert lots1 == 0.10

    # De-leveraged state should be scaled down 50%
    ok2, lots2, msg2 = manager.authorize_order_routing(
        "STATE_22", "GBPUSDm", 0.10, 10_000.0, 482.5, 500.0, socket_latency_ms=45.0, slippage_points=1.0, now_utc=normal_utc
    )
    assert ok2 is True
    assert lots2 == 0.05

    # Quarantined state should be REJECTED
    ok3, lots3, msg3 = manager.authorize_order_routing(
        "STATE_05", "BTCUSDm", 0.10, 10_000.0, 93.0, 100.0, socket_latency_ms=45.0, slippage_points=1.0, now_utc=normal_utc
    )
    assert ok3 is False
    assert lots3 == 0.0
    assert "QUARANTINED" in msg3


def test_rollover_curfew_rejection():
    manager = SupremeCourtCircuitBreakerManager()
    manager.audit_and_enforce_state_pod("STATE_01", "Gold", "XAUUSDm", 500.0, 500.0, 500.0)

    # Rollover curfew time: 22:00 UTC (05:00 ICT)
    curfew_utc = datetime(2026, 9, 28, 22, 0, 0, tzinfo=timezone.utc)

    ok, lots, msg = manager.authorize_order_routing(
        "STATE_01", "XAUUSDm", 0.10, 10_000.0, 500.0, 500.0, now_utc=curfew_utc
    )
    assert ok is False
    assert lots == 0.0
    assert "ROLLOVER_CURFEW" in msg


if __name__ == "__main__":
    pytest.main(["-v", __file__])
