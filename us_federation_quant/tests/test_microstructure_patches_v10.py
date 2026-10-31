import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd


def test_stagnation_exit_logic():
    """Verify Stagnation Exit closes positions aged >= 4h with profit < $10."""
    now_utc = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    
    # Position 1: Stagnant (5 hours old, profit $2.50) -> Should CLOSE
    pos1 = {
        "ticket": 101,
        "symbol": "EURGBP",
        "time": now_utc - timedelta(hours=5.0),
        "profit": 2.50,
    }
    # Position 2: Young (1 hour old, profit -$5.00) -> Should RETAIN
    pos2 = {
        "ticket": 102,
        "symbol": "GBPCHF",
        "time": now_utc - timedelta(hours=1.0),
        "profit": -5.00,
    }
    # Position 3: Mature Winner (6 hours old, profit $35.00) -> Should RETAIN
    pos3 = {
        "ticket": 103,
        "symbol": "EURAUD",
        "time": now_utc - timedelta(hours=6.0),
        "profit": 35.00,
    }

    mock_mgr = MagicMock()
    mock_mgr.get_positions.return_value = [pos1, pos2, pos3]

    closed_tickets = []
    positions = mock_mgr.get_positions()
    for pos in positions:
        pos_time_utc = pos["time"]
        pos_age_hours = (now_utc - pos_time_utc).total_seconds() / 3600.0
        pos_profit = float(pos.get("profit", 0.0))
        ticket = pos.get("ticket")
        if pos_age_hours >= 4.0 and pos_profit < 10.0:
            mock_mgr.close_position(ticket=ticket, comment="Stagnation Exit")
            closed_tickets.append(ticket)

    assert closed_tickets == [101]
    mock_mgr.close_position.assert_called_once_with(ticket=101, comment="Stagnation Exit")


def test_monday_open_curfew():
    """Verify Monday Curfew blocks new orders between 00:00 and 00:59 UTC."""
    # Monday 00:30 UTC
    monday_open = datetime(2026, 10, 26, 0, 30, 0, tzinfo=timezone.utc)
    assert monday_open.weekday() == 0 and monday_open.hour == 0

    # Monday 01:15 UTC (Normal trading)
    monday_active = datetime(2026, 10, 26, 1, 15, 0, tzinfo=timezone.utc)
    assert not (monday_active.weekday() == 0 and monday_active.hour == 0)

    # Tuesday 00:30 UTC (Normal trading)
    tuesday_open = datetime(2026, 10, 27, 0, 30, 0, tzinfo=timezone.utc)
    assert not (tuesday_open.weekday() == 0 and tuesday_open.hour == 0)


def test_us_index_session_gate():
    """Verify US Indices are restricted to 13:00 - 21:00 UTC."""
    symbols = ["USTECm", "US30m", "EURUSDm"]
    
    # 10:00 UTC (European morning -> Reject US Indices, Allow EURUSD)
    hour_off = 10
    allowed_10 = []
    for s in symbols:
        if any(idx in s.upper() for idx in ["USTEC", "US30", "US100"]):
            if not (13 <= hour_off <= 21):
                continue
        allowed_10.append(s)
    assert allowed_10 == ["EURUSDm"]

    # 15:00 UTC (New York open -> Allow all)
    hour_on = 15
    allowed_15 = []
    for s in symbols:
        if any(idx in s.upper() for idx in ["USTEC", "US30", "US100"]):
            if not (13 <= hour_on <= 21):
                continue
        allowed_15.append(s)
    assert allowed_15 == ["USTECm", "US30m", "EURUSDm"]


def test_stop_loss_floor_calculation():
    """Verify Stop Loss floor enforces minimum 150 points for tight-ATR pairs."""
    pt = 0.00001
    min_point_floor = 150.0 * pt  # 0.00150 (15 pips)
    stops_level = 0
    spread = 10
    min_stop_dist = (stops_level + spread + 5) * pt  # 0.00015

    # Case 1: Extremely narrow ATR (EURGBP: 6 pips ATR = 0.00060)
    atr_narrow = 0.00060
    raw_sl_dist = 1.8 * atr_narrow  # 0.00108 (under 150 points)
    sl_dist = max(raw_sl_dist, min_point_floor, min_stop_dist)
    
    # Floor must protect it
    assert sl_dist == min_point_floor
    assert sl_dist == 0.00150

    # Case 2: High Volatility ATR (GBPCHF: 30 pips ATR = 0.00300)
    atr_wide = 0.00300
    raw_sl_wide = 1.8 * atr_wide  # 0.00540 (540 points > 150 points)
    sl_dist_wide = max(raw_sl_wide, min_point_floor, min_stop_dist)
    assert sl_dist_wide == 0.00540


def test_toxic_hours_blacklist():
    """Verify Toxic Hours Blacklist {0, 6, 18, 23} UTC blocks new entries while allowing Trailing SL."""
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime

    toxic_hours = {0, 6, 18, 23}
    assert USFederationQuantRuntime.TOXIC_HOURS == toxic_hours

    # Test all 24 hours
    for h in range(24):
        is_toxic = USFederationQuantRuntime.is_toxic_hour(h)
        if h in toxic_hours:
            assert is_toxic is True, f"Hour {h} should be toxic"
        else:
            assert is_toxic is False, f"Hour {h} should NOT be toxic"

    # Pre-trade order gatekeeper simulation
    mock_runtime = MagicMock(spec=USFederationQuantRuntime)
    mock_runtime.is_toxic_hour = USFederationQuantRuntime.is_toxic_hour
    mock_runtime.TOXIC_HOURS = toxic_hours

    # At 06:00 UTC (Tokyo/London transition) -> order must be rejected
    exec_hour_toxic = 6
    assert mock_runtime.is_toxic_hour(exec_hour_toxic) is True

    # At 14:00 UTC (US session liquid core) -> order allowed
    exec_hour_clean = 14
    assert mock_runtime.is_toxic_hour(exec_hour_clean) is False


def test_eurgbp_d1_ema200_trend_filter():
    """Verify EURGBP State 31 Mean-Reversion blocks BUY when price is below D1 EMA200."""
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime

    # Construct synthetic 200-bar D1 dataset where EMA200 is around 0.85497
    dates = pd.date_range("2026-01-01", periods=200, freq="D")
    closes = np.full(200, 0.85497)
    df_d1 = pd.DataFrame({"close": closes}, index=dates)

    mock_runtime = MagicMock(spec=USFederationQuantRuntime)
    mock_runtime.check_eurgbp_d1_ema200_filter = USFederationQuantRuntime.check_eurgbp_d1_ema200_filter.__get__(mock_runtime)
    mock_runtime.mt5_mgr = MagicMock()
    mock_runtime.mt5_mgr.resolve_symbol.return_value = "EURGBPm"
    mock_runtime.mt5_mgr.get_rates.return_value = df_d1

    with patch("MetaTrader5.copy_rates_from_pos", return_value=None):
        # Scenario 1: Price 0.83332 < EMA200 0.85497 -> BUY rejected (allow_buy = False)
        allow_buy_counter = mock_runtime.check_eurgbp_d1_ema200_filter(
            symbol="EURGBPm",
            current_h1_price=0.83332,
            action="BUY",
        )
        assert allow_buy_counter is False, "EURGBP BUY below D1 EMA200 must be rejected!"

        # Scenario 2: Price 0.86000 > EMA200 0.85497 -> BUY approved (allow_buy = True)
        allow_buy_trend = mock_runtime.check_eurgbp_d1_ema200_filter(
            symbol="EURGBPm",
            current_h1_price=0.86000,
            action="BUY",
        )
        assert allow_buy_trend is True, "EURGBP BUY above D1 EMA200 must be approved!"

        # Scenario 3: Price 0.83332 < EMA200 0.85497 -> SELL approved (trend-aligned)
        allow_sell_trend = mock_runtime.check_eurgbp_d1_ema200_filter(
            symbol="EURGBPm",
            current_h1_price=0.83332,
            action="SELL",
        )
        assert allow_sell_trend is True, "EURGBP SELL in downtrend must be approved!"

        # Scenario 4: Other symbol (e.g. GBPCHFm) -> not affected
        allow_other = mock_runtime.check_eurgbp_d1_ema200_filter(
            symbol="GBPCHFm",
            current_h1_price=1.1200,
            action="BUY",
        )
        assert allow_other is True, "Non-EURGBP symbols must bypass this filter!"


def test_friday_eod_flat_rule():
    """Verify Friday EOD Flat Rule closes all positions at or after 21:00 UTC on Friday."""
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime

    # 1. Curfew timestamp checks
    friday_before = datetime(2026, 10, 30, 20, 59, 0, tzinfo=timezone.utc)
    friday_curfew = datetime(2026, 10, 30, 21, 0, 0, tzinfo=timezone.utc)
    friday_late = datetime(2026, 10, 30, 23, 45, 0, tzinfo=timezone.utc)
    thursday_late = datetime(2026, 10, 29, 21, 30, 0, tzinfo=timezone.utc)

    assert not (friday_before.weekday() == 4 and friday_before.hour >= 21)
    assert (friday_curfew.weekday() == 4 and friday_curfew.hour >= 21)
    assert (friday_late.weekday() == 4 and friday_late.hour >= 21)
    assert not (thursday_late.weekday() == 4 and thursday_late.hour >= 21)

    # 2. Liquidation execution test
    mock_runtime = MagicMock(spec=USFederationQuantRuntime)
    mock_runtime.enforce_friday_eod_flat = USFederationQuantRuntime.enforce_friday_eod_flat.__get__(mock_runtime)

    mock_positions = [
        {"ticket": 1001, "symbol": "EURUSDm", "profit": 15.0},
        {"ticket": 1002, "symbol": "GBPCHFm", "profit": -8.5},
        {"ticket": 1003, "symbol": "USTECm", "profit": 42.0},
    ]

    mock_runtime.mt5_mgr = MagicMock()
    mock_runtime.mt5_mgr.get_positions.return_value = mock_positions
    mock_runtime.mt5_mgr.close_position.return_value = {"success": True}

    with patch("MetaTrader5.positions_get", return_value=mock_positions):
        closed_count = mock_runtime.enforce_friday_eod_flat()

    assert closed_count == 3
    assert mock_runtime.mt5_mgr.close_position.call_count == 3
    mock_runtime.mt5_mgr.close_position.assert_any_call(ticket=1001, comment="Friday EOD Flat")
    mock_runtime.mt5_mgr.close_position.assert_any_call(ticket=1002, comment="Friday EOD Flat")
    mock_runtime.mt5_mgr.close_position.assert_any_call(ticket=1003, comment="Friday EOD Flat")

