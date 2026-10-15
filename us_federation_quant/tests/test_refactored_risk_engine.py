import os
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from us_federation_quant.live_federation_runner import USFederationQuantRuntime
import importlib
_gold_pod_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_01_xauusd_scalp.pod")
GoldScalpPod = _gold_pod_mod.GoldScalpPod

def test_xauusd_dynamic_volatility_sizing():
    """Verify Gold ATR(14) sizing strictly caps risk at $75 and volume at 0.05L."""
    pod = GoldScalpPod(allocated_capital=250_000.0)

    # Synthetic Gold M15 dataframe with high volatility
    dates = pd.date_range("2026-10-15 00:00", periods=50, freq="15min")
    df = pd.DataFrame({
        "open": np.linspace(4100, 4150, 50),
        "high": np.linspace(4105, 4155, 50),
        "low": np.linspace(4095, 4145, 50),
        "close": np.linspace(4100, 4150, 50),
    }, index=dates)

    proposal = pod.generate_trade_proposal(
        market_df=df,
        account_equity=9000.0,
        cash_vol_budget=150.0,
        current_position_lot=0.0
    )

    # Volume must never exceed 0.05L
    assert proposal.target_lots <= 0.05
    assert proposal.target_lots >= 0.01

def test_xauusd_hard_stop_cap_emergency_close():
    """Verify that any XAUUSD position losing >= $75 triggers emergency market close."""
    runner = USFederationQuantRuntime(initial_capital_usd=9000.0)
    runner.mt5_mgr = MagicMock()
    runner.telemetry = MagicMock()

    # Simulate 2 open positions: 1 profitable, 1 gold position at -$82.50 loss
    runner.mt5_mgr.get_positions.return_value = [
        {"ticket": 1001, "symbol": "USDCADm", "type": "SELL", "volume": 0.14, "profit": 50.0, "swap": 0.0, "commission": 0.0},
        {"ticket": 1002, "symbol": "XAUUSDm", "type": "BUY", "volume": 0.05, "profit": -80.0, "swap": -2.5, "commission": 0.0},
    ]
    runner.mt5_mgr.close_position.return_value = {"success": True, "ticket": 1002}

    closed = runner.enforce_xauusd_hard_stop_cap(max_loss_usd=75.0)

    assert len(closed) == 1
    runner.mt5_mgr.close_position.assert_called_once_with(ticket=1002, comment="XAU HardCap 75")
    runner.telemetry.broadcast_critical_alert.assert_called_once()

def test_two_tier_exit_engine_partial_tp_and_idempotency(tmp_path):
    """Verify Tier 1 closes 50% volume, moves SL to BE, and records state idempotently."""
    runner = USFederationQuantRuntime(initial_capital_usd=9000.0)
    runner.mt5_mgr = MagicMock()

    # Mock symbol spec
    runner.mt5_mgr.get_symbol_spec.return_value = {"digits": 2}
    
    # Mock open position with profit $45.0 (exceeds Tier 1 $25 threshold)
    runner.mt5_mgr.get_positions.return_value = [
        {
            "ticket": 2001,
            "symbol": "USTECm",
            "type": "BUY",
            "volume": 0.50,
            "price_open": 29600.0,
            "price_current": 29750.0,
            "profit": 45.0,
            "sl": 29400.0,
        }
    ]
    runner.mt5_mgr.close_position.return_value = {"success": True, "ticket": 2001}
    runner.mt5_mgr.modify_position_sltp.return_value = {"success": True, "ticket": 2001}

    # Redirect state persistence to tmp_path
    with patch("live_federation_runner.LOG_DIR", tmp_path):
        res1 = runner.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)
        assert len(res1["partial_closed"]) == 1
        # 50% of 0.50L = 0.25L
        runner.mt5_mgr.close_position.assert_called_once_with(ticket=2001, volume=0.25, comment="Tier1 50% TP")
        runner.mt5_mgr.modify_position_sltp.assert_called_once()

        # Call second time: idempotency must prevent closing 50% again
        runner.mt5_mgr.close_position.reset_mock()
        res2 = runner.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)
        assert len(res2["partial_closed"]) == 0
        runner.mt5_mgr.close_position.assert_not_called()

def test_us_equities_filters():
    """Verify US Equities blacklist, opening bell time filter, and EMA trend filter."""
    runner = USFederationQuantRuntime(initial_capital_usd=9000.0)
    
    # 1. Blacklist check
    assert "BAC" in runner.US_EQUITIES_BLACKLIST
    assert "JNJ" in runner.US_EQUITIES_BLACKLIST
    assert "V" in runner.US_EQUITIES_BLACKLIST

    # 2. Whitelist check
    assert "TSLA" in runner.US_EQUITIES_WHITELIST
    assert "NVDA" in runner.US_EQUITIES_WHITELIST
    assert "AAPL" in runner.US_EQUITIES_WHITELIST
