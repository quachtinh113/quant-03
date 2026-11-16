"""
Unit Tests for Elite Alpha Rebalancing & 3-Tier Mathematical Invariants (2026-11-16)
Verifies:
1. self.ELITE_ALPHA_SYMBOLS contains exactly {"USDCHF", "AUDUSD", "NZDUSD", "EURAUD", "EURJPY", "UK100"}.
   GBPCHF and GBPUSD are excluded.
2. Major FX ATR SL cap at 28.0 pips yields 0.03L - 0.04L for AUDUSD/NZDUSD under $11.25 budget.
3. Universal Hard Risk Cap <= $14.50 USD is strictly enforced.
4. Multi-Tier Profit Ladder:
   - Tier 1: SL locked at Entry + 1.0 pip (+1.20$ USD lock), trigger +$4.80 in Golden Hours (13-17 UTC).
   - Tier 2: Trigger +$8.50 -> Lock +$4.50, TP +$25.00.
   - Tier 3: Trigger +$14.50 -> Lock +$10.00, TP +$40.00.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from us_federation_quant.live_federation_runner import USFederationQuantRuntime


def test_elite_alpha_symbols_exclusion():
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)
    expected_elite = {"USDCHF", "AUDUSD", "NZDUSD", "EURAUD", "EURJPY", "UK100"}
    assert runtime.ELITE_ALPHA_SYMBOLS == expected_elite
    assert "GBPCHF" not in runtime.ELITE_ALPHA_SYMBOLS
    assert "GBPUSD" not in runtime.ELITE_ALPHA_SYMBOLS
    assert runtime.MAX_HARD_RISK_USD == 14.50


def test_major_fx_sl_capping_and_lot_sizing():
    """Verify AUDUSD and NZDUSD lot sizing at 0.03L - 0.04L with 28.0 pip cap."""
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)

    mock_info = MagicMock()
    mock_info.trade_tick_value = 1.0
    mock_info.trade_tick_size = 0.00001
    mock_info.point = 0.00001
    mock_info.digits = 5
    mock_info.volume_min = 0.01
    mock_info.volume_max = 100.0
    mock_info.volume_step = 0.01

    with patch("MetaTrader5.symbol_info", return_value=mock_info):
        # 28 pips = 280 points.
        # Elite Alpha risk budget = $11.25
        # Lot = 11.25 / (280 * 1.0) = 0.04017 -> 0.04L
        lot = runtime.calculate_risk_adjusted_lot("AUDUSD", sl_points=280.0, max_risk_usd=11.25)
        assert lot == 0.04

        # Expected loss at SL: 280 points * 1.0 * 0.04 = $11.20 <= $14.50
        expected_loss = 280.0 * 1.0 * lot
        assert expected_loss <= 14.50
        assert round(expected_loss, 2) == 11.20

        # Base FX risk budget = $7.50
        # Lot = 7.50 / (280 * 1.0) = 0.0267 -> 0.02L
        base_lot = runtime.calculate_risk_adjusted_lot("EURUSD", sl_points=280.0, max_risk_usd=7.50)
        assert base_lot == 0.02
        assert (280.0 * 1.0 * base_lot) <= 14.50


def test_multi_tier_profit_ladder_thresholds():
    """Test 3-Tier Profit Ladder triggers and SL locks."""
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)

    # Mock open positions
    # Position 1: NZDUSD BUY 0.04L with profit +$5.00 (triggers Tier 1 in golden hour)
    mock_pos = [
        {
            "ticket": 99901,
            "symbol": "NZDUSD",
            "type": "BUY",
            "volume": 0.04,
            "price_open": 0.58500,
            "price_current": 0.58625,
            "sl": 0.58220,
            "tp": 0.59000,
            "profit": 5.00,
            "swap": 0.0,
        },
        # Position 2: AUDUSD BUY 0.04L with profit +$9.00 (triggers Tier 2)
        {
            "ticket": 99902,
            "symbol": "AUDUSD",
            "type": "BUY",
            "volume": 0.04,
            "price_open": 0.65000,
            "price_current": 0.65225,
            "sl": 0.64720,
            "tp": 0.65500,
            "profit": 9.00,
            "swap": 0.0,
        },
        # Position 3: EURAUD BUY 0.04L with profit +$16.00 (triggers Tier 3)
        {
            "ticket": 99903,
            "symbol": "EURAUD",
            "type": "BUY",
            "volume": 0.04,
            "price_open": 1.63000,
            "price_current": 1.63500,
            "sl": 1.62500,
            "tp": 1.64000,
            "profit": 16.00,
            "swap": 0.0,
        },
    ]

    mock_info = MagicMock()
    mock_info.trade_tick_value = 1.0
    mock_info.trade_tick_size = 0.00001
    mock_info.point = 0.00001
    mock_info.digits = 5
    mock_info.spread = 10

    runtime.mt5_mgr = MagicMock()
    runtime.mt5_mgr.get_positions.return_value = mock_pos
    runtime.mt5_mgr.modify_position_sltp.side_effect = lambda ticket, sl, tp: {"success": True, "ticket": ticket, "sl": sl, "tp": tp}

    with patch("MetaTrader5.symbol_info", return_value=mock_info):
        # Test during Golden Hours (14:00 UTC)
        with patch("live_federation_runner.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 11, 16, 14, 0, 0, tzinfo=timezone.utc)
            actions = runtime.manage_multi_tier_profit_ladder()

            assert 99901 in runtime._profit_ladder_locked_tickets
            assert 99902 in runtime._tier2_locked_tickets
            assert 99903 in runtime._tier2_locked_tickets
            assert len(actions) == 3

            # Verify Tier 1: NZDUSD SL moved to Entry + min profit (1.20 / (100000 * 0.04) = 0.00030 -> 0.58530)
            t1_action = next(a for a in actions if a["ticket"] == 99901)
            assert t1_action["sl"] > 0.58500  # Locked in profit
            assert t1_action["sl"] == 0.58530

            # Verify Tier 2: AUDUSD SL locked at +$4.50 USD
            t2_action = next(a for a in actions if a["ticket"] == 99902)
            assert t2_action["sl"] == 0.65113

            # Verify Tier 3: EURAUD SL locked at +$10.00 USD
            t3_action = next(a for a in actions if a["ticket"] == 99903)
            assert t3_action["sl"] == 1.63250
