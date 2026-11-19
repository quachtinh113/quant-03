"""
Unit tests for Daily EOD Clean & Max Holding Time Module (2026-11-17)
Verifies:
1. MAX_HOLD_HOURS = 18.0h: Positions held >= 18h with profit >= 0 are closed with EOD_MAX_HOLD_CLEAN.
2. EOD Clean Window (21:45 - 21:58 UTC):
   - Cash-In Runner: floating_pnl >= +$10.00 USD closed with EOD_CASH_IN_RUNNER.
   - Scratch Flat: held >= 2.0h and profit in [-1.20, +3.00] closed with EOD_FLAT_CLEAN.
3. Daily State Reset at 22:05 UTC resets DAILY_START_BALANCE and cleans tracking tickets.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from us_federation_quant.live_federation_runner import USFederationQuantRuntime


def test_max_hold_hours_18h_clean():
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)
    now_utc = datetime(2026, 11, 17, 10, 0, 0, tzinfo=timezone.utc)

    # Position 1: held 19 hours with profit +$2.50 -> Should be closed
    # Position 2: held 5 hours with profit +$2.50 -> Should NOT be closed
    mock_positions = [
        {
            "ticket": 101,
            "symbol": "EURAUD",
            "type": "BUY",
            "volume": 0.02,
            "profit": 2.50,
            "swap": 0.0,
            "time": now_utc - timedelta(hours=19.0),
        },
        {
            "ticket": 102,
            "symbol": "USDCHF",
            "type": "BUY",
            "volume": 0.03,
            "profit": 2.50,
            "swap": 0.0,
            "time": now_utc - timedelta(hours=5.0),
        },
    ]

    runtime.mt5_mgr = MagicMock()
    runtime.mt5_mgr.get_positions.return_value = mock_positions
    runtime.mt5_mgr.is_market_open.return_value = True
    runtime.mt5_mgr.close_position.return_value = {"success": True}

    actions = runtime.enforce_daily_eod_and_holding_clean(now_utc=now_utc)
    assert 101 in actions["closed_max_hold"]
    assert 102 not in actions["closed_max_hold"]
    runtime.mt5_mgr.close_position.assert_called_once_with(ticket=101, comment="EOD_MAX_HOLD_CLEAN")


def test_eod_clean_window_runner_and_stagnant():
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)
    # EOD clean window: 21:50 UTC
    now_utc = datetime(2026, 11, 17, 21, 50, 0, tzinfo=timezone.utc)

    mock_positions = [
        # Pos 201: Big runner +$12.50 -> Cash-in runner
        {
            "ticket": 201,
            "symbol": "USTEC",
            "type": "SELL",
            "volume": 0.05,
            "profit": 12.50,
            "swap": 0.0,
            "time": now_utc - timedelta(hours=4.0),
        },
        # Pos 202: Stagnant trade +$1.20 held 3.5h -> EOD flat clean
        {
            "ticket": 202,
            "symbol": "EURGBP",
            "type": "SELL",
            "volume": 0.05,
            "profit": 1.20,
            "swap": 0.0,
            "time": now_utc - timedelta(hours=3.5),
        },
        # Pos 203: Fresh trade +$0.50 opened 30m ago -> Do NOT close
        {
            "ticket": 203,
            "symbol": "AUDUSD",
            "type": "BUY",
            "volume": 0.04,
            "profit": 0.50,
            "swap": 0.0,
            "time": now_utc - timedelta(minutes=30),
        },
    ]

    runtime.mt5_mgr = MagicMock()
    runtime.mt5_mgr.get_positions.return_value = mock_positions
    runtime.mt5_mgr.is_market_open.return_value = True
    runtime.mt5_mgr.close_position.return_value = {"success": True}

    actions = runtime.enforce_daily_eod_and_holding_clean(now_utc=now_utc)
    assert 201 in actions["closed_eod_runner"]
    assert 202 in actions["closed_eod_stagnant"]
    assert 203 not in actions["closed_eod_runner"]
    assert 203 not in actions["closed_eod_stagnant"]


def test_daily_state_reset_2205_utc():
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)
    reset_time = datetime(2026, 11, 17, 22, 6, 0, tzinfo=timezone.utc)

    # Set up some dead tickets in tracking sets
    runtime._profit_ladder_locked_tickets = {301, 302, 999}
    runtime._tier2_locked_tickets = {301, 888}

    mock_positions = [
        {"ticket": 301, "symbol": "EURJPY", "type": "SELL", "profit": 0.5, "swap": 0.0, "time": reset_time}
    ]

    runtime.mt5_mgr = MagicMock()
    runtime.mt5_mgr.get_positions.return_value = mock_positions
    runtime.mt5_mgr.get_account_info.return_value = {"balance": 7525.0}
    runtime.mt5_mgr.is_market_open.return_value = True

    actions = runtime.enforce_daily_eod_and_holding_clean(now_utc=reset_time)
    assert actions["daily_reset"] is True
    assert runtime.DAILY_START_BALANCE == 7525.0
    # Dead tickets 999 and 888 must be cleaned
    assert runtime._profit_ladder_locked_tickets == {301}
    assert runtime._tier2_locked_tickets == {301}
