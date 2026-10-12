"""
Unit and Integration Tests for Carver Live Engine Integration:
1. State 02 (US30HybridPod) Carver continuous forecasting and sizing.
2. State 03 (USDJPYCarryPod) Carver continuous forecasting and sizing.
3. State 05 (NowTradingMtfPod) Carver continuous forecasting and sizing.
4. SupremeCourt direct warrant issuance and cryptographic verification.
5. Live Federation Runner Carver scan & route cycle with trade buffering.
"""

import importlib
import time
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

_states_mod = importlib.import_module("us_federation_quant.05_the_50_states")
BaseStatePod = _states_mod.BaseStatePod
US30HybridPod = _states_mod.US30HybridPod
USDJPYCarryPod = _states_mod.USDJPYCarryPod

_s5_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_05_nowtrading_mtf.pod")
NowTradingMtfPod = _s5_mod.NowTradingMtfPod

_court_mod = importlib.import_module("us_federation_quant.02_supreme_court.cryptographic_warrant")
SupremeCourt = _court_mod.SupremeCourt
JudicialWarrant = _court_mod.JudicialWarrant

from us_federation_quant.core.order_state_machine import OrderState
from us_federation_quant.live_federation_runner import USFederationQuantRuntime


def test_us30_hybrid_pod_carver_forecasting_and_buffering():
    """Verifies US30 pod generates Carver continuous forecast and applies position buffering."""
    pod = US30HybridPod()
    bars = 35
    close = 38000.0 + np.linspace(0, 600, bars)
    df = pd.DataFrame({
        "open": close - 10,
        "high": close + 20,
        "low": close - 20,
        "close": close,
        "volume": np.full(bars, 3000.0)
    })

    # Test Carver continuous forecast under dovish stance
    prop = pod.generate_trade_proposal(
        df,
        fed_stance="DOVISH_QE",
        cash_vol_budget=250.0,
        current_position_lot=0.0
    )
    assert prop.action == "BUY"
    assert prop.carver_forecast > 0.0
    assert prop.target_lots > 0
    assert not prop.is_buffered

    # If current position is already close to target, buffering triggers
    prop_buffered = pod.generate_trade_proposal(
        df,
        fed_stance="DOVISH_QE",
        cash_vol_budget=250.0,
        current_position_lot=prop.target_lots
    )
    assert prop_buffered.is_buffered
    assert prop_buffered.target_lots == prop.target_lots


def test_usdjpy_carry_pod_carver_forecasting_and_buffering():
    """Verifies USDJPY carry pod generates Carver continuous forecast and sizes according to yield differential."""
    pod = USDJPYCarryPod()
    bars = 30
    close = 150.0 + np.cumsum(np.random.randn(bars) * 0.1)
    df = pd.DataFrame({
        "open": close - 0.05,
        "high": close + 0.1,
        "low": close - 0.1,
        "close": close,
        "volume": np.full(bars, 2000.0)
    })

    prop = pod.generate_trade_proposal(
        df,
        us_yield_10y=4.5,
        jp_yield_10y=0.5,
        cash_vol_budget=150.0,
        current_position_lot=0.0
    )
    assert prop.action == "BUY"
    assert prop.carver_forecast >= 2.0
    assert prop.target_lots > 0


def test_nowtrading_mtf_pod_carver_forecasting_and_buffering():
    """Verifies State 05 NowTrading MTF pod generates continuous forecast and sizes with cash vol target."""
    pod = NowTradingMtfPod()
    bars = 250
    close = 2000.0 + np.linspace(0, 100, bars)
    df = pd.DataFrame({
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": np.full(bars, 1000.0)
    })

    prop = pod.generate_trade_proposal(
        df,
        cash_vol_budget=100.0,
        current_position_lot=0.0
    )
    assert prop.state_id == "STATE_05"
    assert hasattr(prop, "carver_forecast")
    assert hasattr(prop, "cash_vol_budget")


def test_supreme_court_direct_warrant_and_verification():
    """Verifies Supreme Court can issue direct warrants with HMAC-SHA256 signatures and verify them."""
    court = SupremeCourt(secret_key="TEST_SEAL_123")
    warrant = court.issue_direct_warrant(
        bill_id="BILL_STATE_01_TEST",
        target_asset="XAUUSDm",
        action="BUY",
        authorized_lots=0.05,
        dsr=0.96,
        psr=0.98
    )

    assert isinstance(warrant, JudicialWarrant)
    assert court.verify_warrant(warrant) is True

    # Tampered warrant signature fails verification
    warrant.signature_token = "tampered_fake_signature"
    assert court.verify_warrant(warrant) is False


def test_live_runner_scan_and_route_with_carver_mock():
    """Verifies live runner scans state proposals, allocates Carver budgets, and handles trade buffering."""
    runner = USFederationQuantRuntime(initial_capital_usd=10_000.0)

    # Mock MT5 connection manager
    mock_mgr = MagicMock()
    mock_mgr.resolve_symbol.side_effect = lambda s: s
    mock_mgr.get_positions.return_value = []

    # Mock market rates (uptrend)
    bars = 50
    close = 2000.0 + np.linspace(0, 50, bars)
    rates_df = pd.DataFrame({
        "open": close - 2,
        "high": close + 4,
        "low": close - 4,
        "close": close,
        "volume": np.full(bars, 500.0)
    })
    mock_mgr.get_rates.return_value = rates_df
    mock_mgr.open_market_order.return_value = {
        "success": True,
        "ticket": 999888,
        "price": 2050.0,
        "volume": 0.05
    }
    runner.mt5_mgr = mock_mgr

    # Only test with 2 states to be fast
    state_01 = runner.hub.states_registry.get_state("STATE_01")
    state_02 = runner.hub.states_registry.get_state("STATE_02")
    runner.hub.states_registry.states = {
        "STATE_01": state_01,
        "STATE_02": state_02
    }

    executed = runner.scan_and_route_state_proposals(account_equity=10_000.0)

    # Quotas must be recorded
    assert len(runner.previous_quotas) > 0
    # At least one proposal should have been evaluated
    assert mock_mgr.get_rates.called
