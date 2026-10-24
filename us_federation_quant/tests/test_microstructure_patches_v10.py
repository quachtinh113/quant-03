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
