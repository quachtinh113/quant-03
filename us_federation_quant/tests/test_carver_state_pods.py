"""
========================================================================================
Unit Tests for Robert Carver Continuous Forecasting & Sizing in 50 State Pods (Pha 2)
========================================================================================
"""

import pytest
import numpy as np
import pandas as pd
import importlib

_base_mod = importlib.import_module("us_federation_quant.05_the_50_states.base_pod")
BaseStatePod = _base_mod.BaseStatePod
StateTradeProposal = _base_mod.StateTradeProposal

_gold_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_01_xauusd_scalp.pod")
GoldScalpPod = _gold_mod.GoldScalpPod


def test_base_pod_continuous_forecast_bounds():
    pod = BaseStatePod(
        state_id="STATE_TEST",
        state_name="Test Pod",
        primary_asset="XAUUSDm",
        strategy_style="Mean-Reversion",
        timeframe="M15",
    )

    # 1. Neutral price -> forecast near 0
    close_flat = np.full(50, 2000.0)
    df_flat = pd.DataFrame({"close": close_flat})
    f_flat = pod.calculate_continuous_forecast(df_flat)
    assert f_flat == 0.0

    # 2. Oversold plunge -> bullish mean-reversion forecast (positive)
    close_drop = np.concatenate([np.full(45, 2000.0), [1950.0, 1920.0, 1900.0, 1880.0, 1850.0]])
    df_drop = pd.DataFrame({"close": close_drop})
    f_bullish = pod.calculate_continuous_forecast(df_drop)
    assert f_bullish > 5.0
    assert f_bullish <= 20.0  # Must be strictly capped at +20.0

    # 3. Extreme overbought surge -> capped at -20.0
    close_surge = np.concatenate([np.full(40, 2000.0), np.linspace(2000, 3000, 10)])
    df_surge = pd.DataFrame({"close": close_surge})
    f_bearish = pod.calculate_continuous_forecast(df_surge)
    assert f_bearish == -20.0  # Capped at -20.0


def test_base_pod_carver_target_position_and_buffering():
    pod = BaseStatePod(
        state_id="STATE_TEST",
        state_name="Test Pod",
        primary_asset="XAUUSDm",
        strategy_style="Trend Following",
        timeframe="H1",
    )

    # Target calculation with 10.0 forecast (baseline 1.0x)
    # Cash vol budget = $100, ATR = 10.0, Gold Contract size = 100.0 -> Dollar risk = $1,000
    # Raw lots = (100 * 1.0) / 1000 = 0.10 lots
    res1 = pod.calculate_carver_target_position(
        cash_vol_target=100.0,
        forecast=10.0,
        current_position_lot=0.0,
        atr_price=10.0,
        contract_size=100.0,
        buffer_fraction=0.10,
    )
    assert res1["raw_lots"] == 0.10
    assert res1["buffered_lots"] == 0.10
    assert res1["is_buffered"] is False

    # Target calculation with max forecast 20.0 (2.0x scalar) -> 0.20 lots
    res2 = pod.calculate_carver_target_position(
        cash_vol_target=100.0,
        forecast=20.0,
        current_position_lot=0.0,
        atr_price=10.0,
        contract_size=100.0,
    )
    assert res2["raw_lots"] == 0.20
    assert res2["buffered_lots"] == 0.20

    # Trade Buffering check:
    # Current position is 0.19 lots. Target is 0.20 lots (difference is 0.01 = 5% < 10% buffer)
    # Buffering must trigger -> retain 0.19 lots!
    res_buf = pod.calculate_carver_target_position(
        cash_vol_target=100.0,
        forecast=20.0,
        current_position_lot=0.19,
        atr_price=10.0,
        contract_size=100.0,
        buffer_fraction=0.10,
    )
    assert res_buf["is_buffered"] is True
    assert res_buf["buffered_lots"] == 0.19


def test_gold_scalp_pod_carver_proposal():
    pod = GoldScalpPod(allocated_capital=250_000.0)

    # Mock OHLCV data
    np.random.seed(42)
    n = 60
    prices = 2650.0 + np.cumsum(np.random.normal(0.5, 2.0, n))
    df = pd.DataFrame({
        "open": prices - 1.0,
        "high": prices + 2.0,
        "low": prices - 2.0,
        "close": prices,
        "volume": np.random.uniform(100, 500, n),
    })

    # Generate proposal with Fed cash vol budget
    proposal = pod.generate_trade_proposal(
        market_df=df,
        account_equity=10_000.0,
        cash_vol_budget=150.0,
        current_position_lot=0.0,
    )

    assert isinstance(proposal, StateTradeProposal)
    assert -20.0 <= proposal.carver_forecast <= 20.0
    assert proposal.cash_vol_budget == 150.0
    if proposal.action != "HOLD":
        assert proposal.target_lots > 0.0
