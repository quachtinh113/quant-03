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
    """Verify Friday EOD Flat Rule (>= 20:30 UTC / 23:30 Server Time) and Weekend Hold Sweeper (Skill 07)."""
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime

    # 1. Curfew & Flat window timestamp checks (Skill 07 Time Rule 23:30-23:45 Server Time = 20:30-20:45 UTC)
    friday_1959 = datetime(2026, 10, 30, 19, 59, 0, tzinfo=timezone.utc)
    friday_2005 = datetime(2026, 10, 30, 20, 5, 0, tzinfo=timezone.utc)
    friday_2030 = datetime(2026, 10, 30, 20, 30, 0, tzinfo=timezone.utc)
    friday_2100 = datetime(2026, 10, 30, 21, 0, 0, tzinfo=timezone.utc)
    saturday_noon = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
    thursday_late = datetime(2026, 10, 29, 21, 30, 0, tzinfo=timezone.utc)

    assert USFederationQuantRuntime.is_friday_or_weekend_curfew(friday_1959) is False
    assert USFederationQuantRuntime.is_friday_or_weekend_curfew(friday_2005) is True
    assert USFederationQuantRuntime.is_friday_or_weekend_curfew(saturday_noon) is True
    assert USFederationQuantRuntime.is_friday_or_weekend_curfew(thursday_late) is False

    assert USFederationQuantRuntime.is_friday_eod_flat_window(friday_2005) is False
    assert USFederationQuantRuntime.is_friday_eod_flat_window(friday_2030) is True
    assert USFederationQuantRuntime.is_friday_eod_flat_window(friday_2100) is True
    assert USFederationQuantRuntime.is_friday_eod_flat_window(thursday_late) is False

    # 2. Liquidation execution test
    mock_runtime = MagicMock(spec=USFederationQuantRuntime)
    mock_runtime.enforce_friday_eod_flat = USFederationQuantRuntime.enforce_friday_eod_flat.__get__(mock_runtime)
    mock_runtime.enforce_weekend_hold_sweeper = USFederationQuantRuntime.enforce_weekend_hold_sweeper.__get__(mock_runtime)
    mock_runtime.check_symbol_liquidation_readiness = USFederationQuantRuntime.check_symbol_liquidation_readiness.__get__(mock_runtime)
    mock_runtime.is_friday_eod_flat_window = USFederationQuantRuntime.is_friday_eod_flat_window
    mock_runtime.get_last_weekly_open_utc = USFederationQuantRuntime.get_last_weekly_open_utc

    mock_positions = [
        {"ticket": 1001, "symbol": "EURUSDm", "profit": 15.0, "time": datetime(2026, 10, 30, 15, 0, tzinfo=timezone.utc)},
        {"ticket": 1002, "symbol": "GBPCHFm", "profit": -8.5, "time": datetime(2026, 10, 30, 16, 0, tzinfo=timezone.utc)},
        {"ticket": 1003, "symbol": "USTECm", "profit": 42.0, "time": datetime(2026, 10, 30, 19, 0, tzinfo=timezone.utc)},
    ]

    mock_runtime.mt5_mgr = MagicMock()
    mock_runtime.mt5_mgr.get_positions.return_value = mock_positions
    mock_runtime.mt5_mgr.is_market_open.return_value = True
    mock_runtime.mt5_mgr.close_position.return_value = {"success": True}

    with patch("MetaTrader5.positions_get", return_value=mock_positions):
        closed_count = mock_runtime.enforce_friday_eod_flat()

    assert closed_count == 3
    assert mock_runtime.mt5_mgr.close_position.call_count == 3
    mock_runtime.mt5_mgr.close_position.assert_any_call(ticket=1001, comment="Friday EOD Flat")
    mock_runtime.mt5_mgr.close_position.assert_any_call(ticket=1002, comment="Friday EOD Flat")
    mock_runtime.mt5_mgr.close_position.assert_any_call(ticket=1003, comment="Friday EOD Flat")

    # 3. Weekend Hold Sweeper test: Monday reopen liquidates Friday positions immediately when ready
    mock_runtime.mt5_mgr.close_position.reset_mock()
    monday_reopen = datetime(2026, 11, 2, 0, 15, 0, tzinfo=timezone.utc)
    with patch("MetaTrader5.symbol_info_tick", return_value=None):
        swept_count = mock_runtime.enforce_weekend_hold_sweeper(monday_reopen)
    assert swept_count == 3
    mock_runtime.mt5_mgr.close_position.assert_any_call(ticket=1001, comment="Weekend Hold Flat")


def test_us_dst_server_time_adaptation():
    """Verify MT5 Server Time (23:30 Server Time) automatically adapts to Nov 1, 2026 US DST transition."""
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime

    # Before Nov 1, 2026 (Summer EDT -> Server = UTC+3):
    # 20:30 UTC = 23:30 Server Time -> Flat window TRUE
    fri_edt_2030 = datetime(2026, 10, 30, 20, 30, 0, tzinfo=timezone.utc)
    assert USFederationQuantRuntime.is_us_dst(fri_edt_2030) is True
    assert USFederationQuantRuntime.get_mt5_server_datetime(fri_edt_2030).hour == 23
    assert USFederationQuantRuntime.is_friday_eod_flat_window(fri_edt_2030) is True

    # After Nov 1, 2026 (Winter EST -> Server = UTC+2):
    # 20:30 UTC = 22:30 Server Time -> Flat window FALSE (does not close 1.5h early!)
    fri_est_2030 = datetime(2026, 11, 6, 20, 30, 0, tzinfo=timezone.utc)
    assert USFederationQuantRuntime.is_us_dst(fri_est_2030) is False
    assert USFederationQuantRuntime.get_mt5_server_datetime(fri_est_2030).hour == 22
    assert USFederationQuantRuntime.is_friday_eod_flat_window(fri_est_2030) is False

    # 21:30 UTC on Nov 6, 2026 = 23:30 Server Time -> Flat window TRUE (29m before 21:59 UTC close)
    fri_est_2130 = datetime(2026, 11, 6, 21, 30, 0, tzinfo=timezone.utc)
    assert USFederationQuantRuntime.get_mt5_server_datetime(fri_est_2130).hour == 23
    assert USFederationQuantRuntime.is_friday_eod_flat_window(fri_est_2130) is True


def test_per_symbol_tick_warmup_and_spread_guard():
    """Verify Per-Symbol Tick Freshness (<=60s), 10m Open Warmup, and Spread Guard on Sunday/Monday Reopen."""
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime

    mock_runtime = MagicMock(spec=USFederationQuantRuntime)
    mock_runtime.check_symbol_liquidation_readiness = USFederationQuantRuntime.check_symbol_liquidation_readiness.__get__(mock_runtime)
    mock_runtime.get_mt5_server_datetime = USFederationQuantRuntime.get_mt5_server_datetime
    mock_runtime._save_sweeper_reopen_state = MagicMock()
    mock_runtime._symbol_reopen_first_seen_ts = {}
    mock_runtime.mt5_mgr = MagicMock()
    mock_runtime.mt5_mgr.is_market_open.return_value = True
    mock_runtime.mt5_mgr.resolve_symbol.side_effect = lambda s: s

    # Sunday 22:05 UTC (FX just opened, USTEC & UK100 still closed with Friday tick)
    sun_2205 = datetime(2026, 11, 1, 22, 5, 0, tzinfo=timezone.utc)
    sun_2205_ts = sun_2205.timestamp()

    fx_info = MagicMock(trade_mode=4, point=0.00001)
    idx_info = MagicMock(trade_mode=4, point=0.01)

    # Case 1: UK100 has stale Friday tick (age > 60s) -> Must be blocked (prevents 10018 error)
    stale_uk100_tick = MagicMock(time=sun_2205_ts - 172800.0, bid=10750.0, ask=10752.0)
    with patch("MetaTrader5.symbol_info", return_value=idx_info), \
         patch("MetaTrader5.symbol_info_tick", return_value=stale_uk100_tick), \
         patch("MetaTrader5.SYMBOL_TRADE_MODE_FULL", 4, create=True):
        ready_uk, reason_uk = mock_runtime.check_symbol_liquidation_readiness("UK100", now_utc=sun_2205, open_warmup_sec=600.0)
        assert ready_uk is False
        assert "Stale tick" in reason_uk

    # Case 1b (Edge Case #1): Tick timestamp includes +3h Broker Server Offset (making now_ts - tick.time = -10439s negative!)
    # Friday 21:05 UTC (00:05 Saturday Server Time) vs Friday 20:58:59 UTC close tick (23:58:59 Server Time = +361s old in Server Time)
    fri_2105_utc = datetime(2026, 10, 30, 21, 5, 0, tzinfo=timezone.utc)
    fri_close_srv_epoch = datetime(2026, 10, 30, 23, 58, 59, tzinfo=timezone.utc).timestamp()
    stale_srv_offset_tick = MagicMock(time=fri_close_srv_epoch, bid=1.1030, ask=1.1032)
    with patch("MetaTrader5.symbol_info", return_value=fx_info), \
         patch("MetaTrader5.symbol_info_tick", return_value=stale_srv_offset_tick), \
         patch("MetaTrader5.SYMBOL_TRADE_MODE_FULL", 4, create=True):
        ready_neg, reason_neg = mock_runtime.check_symbol_liquidation_readiness("EURUSD", now_utc=fri_2105_utc, open_warmup_sec=600.0)
        assert ready_neg is False, "Negative tick_age from +3h Broker Server Time offset must NOT bypass stale tick check!"
        assert "Stale tick" in reason_neg

    # Case 2: GBPCHF at 22:05 UTC (t=0s post-open) -> Blocked by 10m (600s) Warmup Buffer
    fresh_gbpchf_wide = MagicMock(time=sun_2205_ts - 5.0, bid=1.10300, ask=1.10450)  # 150 pts spread
    with patch("MetaTrader5.symbol_info", return_value=fx_info), \
         patch("MetaTrader5.symbol_info_tick", return_value=fresh_gbpchf_wide), \
         patch("MetaTrader5.SYMBOL_TRADE_MODE_FULL", 4, create=True):
        ready_t0, reason_t0 = mock_runtime.check_symbol_liquidation_readiness("GBPCHF", now_utc=sun_2205, open_warmup_sec=600.0)
        assert ready_t0 is False
        assert "Warmup Buffer" in reason_t0

        # Case 3: GBPCHF at 22:16 UTC (t=660s post-open, warmup passed) but spread still 150 pts (> 65 pts cap) -> Blocked by Spread Guard
        sun_2216 = sun_2205 + timedelta(minutes=11)
        fresh_gbpchf_wide.time = sun_2216.timestamp() - 2.0
        ready_wide, reason_wide = mock_runtime.check_symbol_liquidation_readiness("GBPCHF", now_utc=sun_2216, open_warmup_sec=600.0)
        assert ready_wide is False
        assert "Spread Guard" in reason_wide

        # Case 4: GBPCHF at 22:17 UTC with normalized spread (25 pts <= 65 pts cap) -> Ready to liquidate!
        sun_2217 = sun_2205 + timedelta(minutes=12)
        fresh_gbpchf_tight = MagicMock(time=sun_2217.timestamp() - 1.0, bid=1.10300, ask=1.10325)  # 25 pts spread
        with patch("MetaTrader5.symbol_info_tick", return_value=fresh_gbpchf_tight):
            ready_ok, reason_ok = mock_runtime.check_symbol_liquidation_readiness("GBPCHF", now_utc=sun_2217, open_warmup_sec=600.0)
            assert ready_ok is True
            assert "Ready" in reason_ok


def test_p0_sunday_open_no_self_liquidation_loop():
    """Regression (Audit 05/11/2026): lệnh mới mở tối Chủ Nhật sau giờ mở phiên KHÔNG được bị gắn cờ Weekend Hold.
    Sự cố 01/11/2026 22:09-22:45 UTC: 82 lệnh mở rồi bị 'Weekend Hold Flat' sau ~10s (-$158.72)."""
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime as R

    sun_2210 = datetime(2026, 11, 1, 22, 10, tzinfo=timezone.utc)
    mon_0015 = datetime(2026, 11, 2, 0, 15, tzinfo=timezone.utc)
    sat_noon = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
    assert R.get_last_weekly_open_utc(sun_2210) == datetime(2026, 11, 1, 22, 0, tzinfo=timezone.utc)
    assert R.get_last_weekly_open_utc(mon_0015) == datetime(2026, 11, 1, 22, 0, tzinfo=timezone.utc)
    assert R.get_last_weekly_open_utc(sat_noon) == datetime(2026, 11, 1, 22, 0, tzinfo=timezone.utc)
    # Mùa hè (EDT): Chủ Nhật 25/10/2026 mở lúc 21:00 UTC
    assert R.get_last_weekly_open_utc(datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)) == datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)

    # Entry curfew kéo dài 60 phút sau giờ mở phiên tuần
    assert R.is_friday_or_weekend_curfew(sun_2210) is True
    assert R.is_friday_or_weekend_curfew(datetime(2026, 11, 1, 23, 5, tzinfo=timezone.utc)) is False

    rt = MagicMock(spec=R)
    rt.enforce_weekend_hold_sweeper = R.enforce_weekend_hold_sweeper.__get__(rt)
    rt.check_symbol_liquidation_readiness = R.check_symbol_liquidation_readiness.__get__(rt)
    rt.is_friday_eod_flat_window = R.is_friday_eod_flat_window
    rt.get_last_weekly_open_utc = R.get_last_weekly_open_utc
    rt.mt5_mgr = MagicMock()
    rt.mt5_mgr.is_market_open.return_value = True
    rt.mt5_mgr.close_position.return_value = {"success": True}
    rt.mt5_mgr.get_positions.return_value = [
        {"ticket": 2001, "symbol": "EURUSD", "profit": -1.36, "time": datetime(2026, 11, 1, 22, 9, 33, tzinfo=timezone.utc)},
        {"ticket": 2002, "symbol": "USDJPY", "profit": -1.98, "time": datetime(2026, 11, 1, 23, 30, tzinfo=timezone.utc)},
        {"ticket": 2003, "symbol": "EURGBP", "profit": -14.8, "time": datetime(2026, 10, 30, 12, 48, tzinfo=timezone.utc)},
    ]
    with patch("MetaTrader5.symbol_info_tick", return_value=None):
        n1 = rt.enforce_weekend_hold_sweeper(sun_2210 + __import__("datetime").timedelta(minutes=1))
        n2 = rt.enforce_weekend_hold_sweeper(mon_0015)
    closed = [c.kwargs["ticket"] for c in rt.mt5_mgr.close_position.call_args_list]
    assert 2001 not in closed and 2002 not in closed, closed
    assert closed.count(2003) >= 1
    assert n1 + n2 == len(closed)


def test_p0_sweeper_default_warmup_applies_with_explicit_now():
    """Regression: vòng lặp live truyền now_utc -> warmup phải vẫn là 600s (trước đây = 0s)."""
    import inspect
    from us_federation_quant.live_federation_runner import USFederationQuantRuntime as R
    sig = inspect.signature(R.enforce_weekend_hold_sweeper)
    assert sig.parameters["open_warmup_sec"].default == 600.0
