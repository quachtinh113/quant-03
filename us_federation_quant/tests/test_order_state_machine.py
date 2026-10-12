"""
========================================================================================
Unit Tests for Nautilus-Inspired Order State Machine & Idempotency Engine
(Giai đoạn 1: Chuẩn hóa Order State Machine, Quota Clawback & Idempotency)
========================================================================================
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from us_federation_quant.core.order_state_machine import (
    OrderState,
    FederationOrder,
    OrderStateMachine,
    OrderReconciliationManager,
    generate_client_order_id,
    InvalidStateTransitionError,
    DuplicateOrderSubmissionError,
)
from us_federation_quant.core.mt5_connection_manager import MT5ConnectionManager
import importlib

_court_mod = importlib.import_module("us_federation_quant.02_supreme_court.cryptographic_warrant")
JudicialWarrant = _court_mod.JudicialWarrant

_router_mod = importlib.import_module("us_federation_quant.03_executive_presidency.order_router.router")
ExecutiveOrderRouter = _router_mod.ExecutiveOrderRouter
MicroOrderSlice = _router_mod.MicroOrderSlice

_bridge_mod = importlib.import_module("us_federation_quant.03_executive_presidency.broker_bridge.mt5_payload_builder")
MT5PayloadBuilder = _bridge_mod.MT5PayloadBuilder


# --------------------------------------------------------------------------------------
# 1. State Machine FSM Transitions Tests
# --------------------------------------------------------------------------------------

def test_order_creation_initial_state():
    cid = generate_client_order_id(magic=260901)
    order = FederationOrder(
        client_order_id=cid,
        symbol="XAUUSDm",
        direction="BUY",
        volume=0.10,
        magic=260901,
    )
    assert order.state == OrderState.PENDING_SUBMIT
    assert order.is_terminal is False
    assert order.filled_volume == 0.0
    assert order.remaining_volume == 0.10
    assert len(order.state_history) == 1
    assert order.state_history[0][0] == OrderState.PENDING_SUBMIT


def test_valid_order_full_fill_lifecycle():
    cid = generate_client_order_id(magic=260901)
    order = FederationOrder(
        client_order_id=cid,
        symbol="XAUUSDm",
        direction="BUY",
        volume=0.10,
        magic=260901,
    )

    # 1. PENDING_SUBMIT -> SUBMITTED
    OrderStateMachine.transition(order, OrderState.SUBMITTED)
    assert order.state == OrderState.SUBMITTED

    # 2. SUBMITTED -> ACCEPTED
    OrderStateMachine.transition(order, OrderState.ACCEPTED)
    assert order.state == OrderState.ACCEPTED

    # 3. Apply full fill -> FILLED
    OrderStateMachine.apply_fill(order, price=2650.50, volume=0.10, ticket=123456)
    assert order.state == OrderState.FILLED
    assert order.is_terminal is True
    assert order.ticket == 123456
    assert order.filled_volume == 0.10
    assert order.remaining_volume == 0.0
    assert len(order.fills) == 1


def test_partial_fill_lifecycle():
    cid = generate_client_order_id(magic=260901)
    order = FederationOrder(
        client_order_id=cid,
        symbol="XAUUSDm",
        direction="BUY",
        volume=1.00,
        magic=260901,
    )

    OrderStateMachine.transition(order, OrderState.SUBMITTED)
    OrderStateMachine.apply_fill(order, price=2650.0, volume=0.40, ticket=999)

    assert order.state == OrderState.PARTIALLY_FILLED
    assert order.filled_volume == 0.40
    assert order.remaining_volume == 0.60
    assert order.is_terminal is False

    # Second partial fill that completes the order
    OrderStateMachine.apply_fill(order, price=2650.2, volume=0.60)
    assert order.state == OrderState.FILLED
    assert order.filled_volume == 1.00
    assert order.remaining_volume == 0.0
    assert order.is_terminal is True


def test_illegal_state_transition_raises_error():
    cid = generate_client_order_id(magic=260901)
    order = FederationOrder(
        client_order_id=cid,
        symbol="XAUUSDm",
        direction="BUY",
        volume=0.10,
    )

    # Cannot jump directly from PENDING_SUBMIT to FILLED
    with pytest.raises(InvalidStateTransitionError):
        OrderStateMachine.transition(order, OrderState.FILLED)

    # Submit order, then reject it
    OrderStateMachine.transition(order, OrderState.SUBMITTED)
    OrderStateMachine.transition(order, OrderState.REJECTED, reason="Insufficient margin")
    assert order.state == OrderState.REJECTED
    assert order.reject_reason == "Insufficient margin"

    # Terminal state cannot transition to anything
    with pytest.raises(InvalidStateTransitionError):
        OrderStateMachine.transition(order, OrderState.SUBMITTED)

    with pytest.raises(InvalidStateTransitionError):
        OrderStateMachine.apply_fill(order, price=2650.0, volume=0.10)


# --------------------------------------------------------------------------------------
# 2. Idempotency & Reconciliation Manager Tests
# --------------------------------------------------------------------------------------

def test_reconciliation_manager_idempotency_prevention():
    reconciler = OrderReconciliationManager()
    cid = "FED-260901-FIXEDID123"

    # First registration should succeed
    order1 = reconciler.register_order(
        symbol="XAUUSDm",
        direction="BUY",
        volume=0.10,
        magic=260901,
        client_order_id=cid,
    )
    assert order1.client_order_id == cid
    assert order1.state == OrderState.PENDING_SUBMIT

    # Re-submitting the exact same active order must raise DuplicateOrderSubmissionError
    with pytest.raises(DuplicateOrderSubmissionError):
        reconciler.register_order(
            symbol="XAUUSDm",
            direction="BUY",
            volume=0.10,
            magic=260901,
            client_order_id=cid,
        )

    # Once order is marked FILLED (terminal), re-registration with same CID is allowed or handled
    reconciler.mark_submitted(cid)
    reconciler.mark_filled(cid, price=2650.0, volume=0.10, ticket=888)
    assert reconciler.get_order(cid).state == OrderState.FILLED


def test_reconciliation_lookup_by_ticket():
    reconciler = OrderReconciliationManager()
    cid = "FED-260901-TICKETCHECK"

    reconciler.register_order(
        symbol="XAUUSDm",
        direction="BUY",
        volume=0.50,
        magic=260901,
        client_order_id=cid,
    )
    reconciler.mark_submitted(cid)
    reconciler.mark_filled(cid, price=2651.0, volume=0.50, ticket=777888)

    matched = reconciler.get_order_by_ticket(777888)
    assert matched is not None
    assert matched.client_order_id == cid
    assert matched.volume == 0.50


# --------------------------------------------------------------------------------------
# 3. Router & MT5 Payload Builder ClientOrderId Integration
# --------------------------------------------------------------------------------------

class DummyWarrant:
    warrant_id = "WARR-TEST-12345678"
    target_asset = "XAUUSDm"
    action = "BUY"
    authorized_lots = 0.50

    def verify_token(self, key="SUPREME_COURT_SEAL"):
        return True


def test_router_generates_deterministic_client_order_ids():
    router = ExecutiveOrderRouter()
    warrant = DummyWarrant()

    from us_federation_quant.institutional_governance_rules import StatutoryAuditResult
    mock_audit = StatutoryAuditResult(is_compliant=True, statute_code="AUDIT", statute_name="PASS", details="Test ok")

    with patch("us_federation_quant.institutional_governance_rules.InstitutionalStatutoryRules.check_rollover_curfew", return_value=mock_audit):
        slices = router.route_execution(
            warrant=warrant,
            market_mid_price=2650.0,
            slices=5,
            execution_strategy="TWAP",
        )

    assert len(slices) == 5
    for i, s in enumerate(slices, start=1):
        assert s.client_order_id.startswith("TWAP-WARR-TES-S")
        assert len(s.client_order_id) <= 31
        assert s.parent_warrant_id == "WARR-TEST-12345678"

    builder = MT5PayloadBuilder()
    batch = builder.build_batch_requests(slices)
    assert len(batch) == 5
    for i, req in enumerate(batch):
        assert req["comment"] == slices[i].client_order_id


# --------------------------------------------------------------------------------------
# 4. Nautilus Quota Clawback & Cascading Failure Protection
# --------------------------------------------------------------------------------------

def test_nautilus_quota_clawback_on_slice_failure():
    reconciler = OrderReconciliationManager()
    warrant_id = "WARR-FED-CLAWBACK-99"

    # Register 3 slices under the same parent warrant
    slice_1 = reconciler.register_order(
        symbol="XAUUSDm", direction="BUY", volume=0.20,
        client_order_id="SLICE-1", parent_warrant_id=warrant_id, slice_index=1, total_slices=3
    )
    slice_2 = reconciler.register_order(
        symbol="XAUUSDm", direction="BUY", volume=0.20,
        client_order_id="SLICE-2", parent_warrant_id=warrant_id, slice_index=2, total_slices=3
    )
    slice_3 = reconciler.register_order(
        symbol="XAUUSDm", direction="BUY", volume=0.20,
        client_order_id="SLICE-3", parent_warrant_id=warrant_id, slice_index=3, total_slices=3
    )

    # Slice 1 fills successfully
    reconciler.mark_submitted("SLICE-1")
    reconciler.mark_filled("SLICE-1", price=2650.0, volume=0.20, ticket=10101)
    assert slice_1.state == OrderState.FILLED

    # Slice 2 is submitted, but fails due to broker slippage cap exceeded
    reconciler.mark_submitted("SLICE-2")
    failure_result = reconciler.handle_slice_failure(
        client_order_id="SLICE-2",
        error_reason="Slippage 2.4 pips breached max cap 1.5 pips",
        auto_clawback=True
    )

    assert failure_result["status"] == "SLICE_REJECTED_QUOTA_REVOKED"
    assert slice_2.state == OrderState.REJECTED
    assert slice_2.reject_reason == "Slippage 2.4 pips breached max cap 1.5 pips"

    # Crucial check: Slice 3 MUST BE AUTOMATICALLY CANCELED (Clawed back)
    assert slice_3.state == OrderState.CANCELED
    assert "Cascading abort" in slice_3.cancel_reason
    assert failure_result["clawback_report"]["clawed_back_lots"] == 0.20
    assert "SLICE-3" in failure_result["clawback_report"]["aborted_client_order_ids"]


def test_judicial_warrant_revocation():
    warrant = JudicialWarrant(
        warrant_id="WARR-REVOKE-TEST",
        bill_id="BILL-01",
        target_asset="XAUUSDm",
        action="BUY",
        authorized_lots=1.0,
        dsr=2.5,
        psr=0.98,
        max_drawdown=-0.02,
        trials_count=10,
        factor_neutrality_verified=True,
        black_swan_scenarios_passed=5,
        timestamp=time.time(),
        signature_token=""
    )
    # Compute valid signature token
    import hmac, hashlib
    payload = (
        f"{warrant.warrant_id}:{warrant.bill_id}:{warrant.target_asset}:{warrant.action}:"
        f"{warrant.authorized_lots}:{warrant.dsr}:{warrant.psr}:{warrant.trials_count}:"
        f"{warrant.factor_neutrality_verified}:{warrant.black_swan_scenarios_passed}:{warrant.timestamp}"
    )
    warrant.signature_token = hmac.new(b"SUPREME_COURT_SEAL", payload.encode(), hashlib.sha256).hexdigest()

    assert warrant.verify_token("SUPREME_COURT_SEAL") is True

    # Revoke warrant
    warrant.revoke("EXECUTION_BREACH_QUOTA_CLAWBACK")
    assert warrant.is_revoked is True
    assert warrant.verify_token("SUPREME_COURT_SEAL") is False


# --------------------------------------------------------------------------------------
# 5. MT5ConnectionManager Idempotency & Order State Integration
# --------------------------------------------------------------------------------------

def test_mt5_connection_manager_order_state_machine_flow():
    mgr = MT5ConnectionManager()
    mgr.connected = True
    mgr.reconciler.clear()

    mgr.get_symbol_spec = MagicMock(return_value={
        "digits": 2, "point": 0.01, "volume_min": 0.01,
        "volume_max": 100.0, "volume_step": 0.01, "contract_size": 100.0,
        "spread_points": 15
    })
    mgr.get_tick = MagicMock(return_value={"bid": 2650.0, "ask": 2650.2, "spread": 0.2, "time": time.time()})

    mock_res = MagicMock()
    mock_res.retcode = 10009  # TRADE_RETCODE_DONE
    mock_res.order = 998877
    mock_res.price = 2650.2
    mock_res.volume = 0.10

    with patch("us_federation_quant.core.mt5_connection_manager.mt5") as mock_mt5:
        mock_mt5.TRADE_RETCODE_DONE = 10009
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TIME_GTC = 0
        mock_mt5.ORDER_FILLING_IOC = 1
        mock_mt5.order_send.return_value = mock_res

        cid = "FED-260901-MOCKTEST1"
        res = mgr.open_market_order(
            symbol="XAUUSDm",
            direction="BUY",
            volume=0.10,
            magic=260901,
            client_order_id=cid,
        )

        assert res["success"] is True
        assert res["client_order_id"] == cid
        assert res["state"] == OrderState.FILLED.value
        assert res["ticket"] == 998877

        cached_order = mgr.reconciler.get_order(cid)
        assert cached_order is not None
        assert cached_order.state == OrderState.FILLED
        assert cached_order.ticket == 998877
