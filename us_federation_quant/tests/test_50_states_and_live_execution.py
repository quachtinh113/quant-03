"""
Unit and Integration Tests for Option 2:
The 50 States Strategy Fleet, MT5 Live Broker Connector, and The Fourth Estate TCA Monitor.
Tests:
1. GoldScalpPod (State 01 XAUUSD) autonomous proposal generation.
2. US30HybridPod (State 02 US30) momentum & FED monetary policy alignment.
3. USDJPYCarryPod (State 03 USDJPY) yield differential carry trading.
4. Localized Drawdown Ladder (-3% de-leverage, -5% quarantine) and reinstatement.
5. Cross-State correlation tracking and redundant risk detection.
6. MT5LiveConnector paper/mock gateway execution and position management.
7. TCAMonitor (The Fourth Estate) execution shortfall and slippage anomaly alerting.
"""

import importlib
import pytest
import numpy as np
import pandas as pd

_states_mod = importlib.import_module("us_federation_quant.05_the_50_states")
StateFederationRegistry = _states_mod.StateFederationRegistry
BaseStatePod = _states_mod.BaseStatePod
StateTradeProposal = _states_mod.StateTradeProposal
GoldScalpPod = _states_mod.GoldScalpPod
US30HybridPod = _states_mod.US30HybridPod
USDJPYCarryPod = _states_mod.USDJPYCarryPod

_exec_mod = importlib.import_module("us_federation_quant.03_executive_presidency")
MT5PayloadBuilder = _exec_mod.MT5PayloadBuilder
MT5LiveConnector = _exec_mod.MT5LiveConnector
MT5RetCode = _exec_mod.MT5RetCode
TCAMonitor = _exec_mod.TCAMonitor
SlippageAnomalyAlert = _exec_mod.SlippageAnomalyAlert
MicroOrderSlice = _exec_mod.MicroOrderSlice


# ---------------------------------------------------------
# 1. State 01: GoldScalpPod Tests
# ---------------------------------------------------------

def test_gold_scalp_pod_proposal():
    """
    Test GoldScalpPod generating an autonomous trade proposal on XAUUSD.
    """
    pod = GoldScalpPod(allocated_capital=250_000.0)
    assert pod.primary_asset == "XAUUSD"
    assert pod.is_active is True

    # Generate bullish price series
    bars = 30
    close = 2000.0 + np.linspace(0, 15, bars)
    df = pd.DataFrame({
        "open": close - 0.5,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": np.full(bars, 1500.0)
    })

    proposal = pod.generate_trade_proposal(df)
    assert isinstance(proposal, StateTradeProposal)
    assert proposal.asset == "XAUUSD"
    assert proposal.action in ["BUY", "SELL", "HOLD"]
    if proposal.action != "HOLD":
        assert proposal.target_lots > 0
        assert proposal.confidence >= 0.60


# ---------------------------------------------------------
# 2. State 02: US30HybridPod & FED Alignment Tests
# ---------------------------------------------------------

def test_us30_hybrid_pod_and_fed_blocking():
    """
    Test US30HybridPod: Trend following works under neutral/QE,
    but gets blocked when FED is running aggressive QT.
    """
    pod = US30HybridPod()
    bars = 35
    # Strong upward trend
    close = 38000.0 + np.linspace(0, 500, bars)
    df = pd.DataFrame({
        "open": close - 10,
        "high": close + 20,
        "low": close - 20,
        "close": close,
        "volume": np.full(bars, 3000.0)
    })

    # Under Dovish / Neutral monetary stance -> Strong BUY
    prop_neutral = pod.generate_trade_proposal(df, fed_stance="DOVISH_EASING")
    assert prop_neutral.action == "BUY"
    assert prop_neutral.target_lots > 0

    # Under Aggressive Quantitative Tightening -> Blocked with HOLD
    prop_qt = pod.generate_trade_proposal(df, fed_stance="QT_QUANTITATIVE_TIGHTENING")
    assert prop_qt.action == "HOLD"
    assert "blocked by Federal Reserve" in prop_qt.rationale


# ---------------------------------------------------------
# 3. State 03: USDJPYCarryPod Tests
# ---------------------------------------------------------

def test_usdjpy_carry_pod():
    """
    Test USDJPYCarryPod capitalizing on positive sovereign yield spread.
    """
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

    # Positive carry: US yield 4.5% vs JP yield 0.5% (gap = 4.0% > 2.5%)
    prop = pod.generate_trade_proposal(df, us_yield_10y=4.5, jp_yield_10y=0.5)
    assert prop.asset == "USDJPY"
    assert prop.action == "BUY"
    assert "Positive Carry" in prop.rationale


# ---------------------------------------------------------
# 4. State Drawdown Ladder & Quarantine Tests
# ---------------------------------------------------------

def test_state_drawdown_ladder_and_quarantine():
    """
    Test constitutional drawdown ladder:
    - Drawdown <= -3% -> cut capital multiplier to 0.50
    - Drawdown <= -5% -> quarantine pod (is_active = False, capital_multiplier = 0.0)
    - Reinstatement restores pod to active state.
    """
    pod = BaseStatePod(
        state_id="TEST_STATE",
        state_name="Test Pod",
        primary_asset="EURUSD",
        strategy_style="Mean-Reversion",
        timeframe="H1",
        allocated_capital=100_000.0
    )

    # Mild loss -1.5% -> Normal
    pod.update_performance(-0.015)
    assert pod.is_active is True
    assert pod.capital_multiplier == 1.0

    # Loss reaches -3.5% (breaches -3% de-leveraging gate)
    pod.update_performance(-0.020)
    assert pod.local_drawdown <= -0.03
    assert pod.capital_multiplier == 0.50
    assert pod.is_active is True

    # Loss reaches -5.5% (breaches -5% quarantine gate)
    pod.update_performance(-0.020)
    assert pod.local_drawdown <= -0.05
    assert pod.is_active is False
    assert pod.is_quarantined is True
    assert pod.capital_multiplier == 0.0

    # Reinstatement
    pod.reinstate(reset_drawdown=True)
    assert pod.is_active is True
    assert pod.is_quarantined is False
    assert pod.local_drawdown == 0.0
    assert pod.capital_multiplier == 1.0


# ---------------------------------------------------------
# 5. Cross-State Correlation Audit Tests
# ---------------------------------------------------------

def test_cross_state_correlation_audit():
    """
    Test StateFederationRegistry audits cross-state correlation
    and flags redundant risk when correlation > 0.85.
    """
    registry = StateFederationRegistry()

    # Highly correlated returns (e.g. Gold and Silver)
    np.random.seed(42)
    common_factor = np.random.randn(50)
    r_gold = common_factor * 0.9 + np.random.randn(50) * 0.1
    r_silver = common_factor * 0.9 + np.random.randn(50) * 0.1
    r_us30 = np.random.randn(50)  # Independent

    returns_dict = {
        "STATE_01": pd.Series(r_gold),
        "STATE_08": pd.Series(r_silver),
        "STATE_02": pd.Series(r_us30)
    }

    audit = registry.audit_cross_state_correlations(returns_dict, max_corr_threshold=0.85)
    assert audit["redundant_pairs_count"] > 0
    assert audit["status"] == "REDUNDANT_RISK_WARNING"
    assert audit["high_correlation_pairs"][0]["state_1"] == "STATE_01"
    assert audit["high_correlation_pairs"][0]["state_2"] == "STATE_08"


# ---------------------------------------------------------
# 6. MT5 Live Connector Paper/Mock Gateway Tests
# ---------------------------------------------------------

def test_mt5_live_connector_paper_gateway():
    """
    Test MT5LiveConnector managing paper positions and account info.
    """
    connector = MT5LiveConnector(account=12345678, force_mock=True)
    assert connector.connect() is True
    assert connector.is_connected is True

    # Account info
    acc = connector.get_account_info()
    assert acc["balance"] == 1_000_000.0
    assert acc["trade_mode"] == "MOCK_PAPER"

    # Send order
    req = {
        "action": 1,
        "symbol": "XAUUSD",
        "volume": 1.5,
        "type": 0,
        "price": 2045.50,
        "sl": 2025.0,
        "tp": 2085.0,
        "deviation": 15,
        "magic": 20260919,
        "comment": "STATE_01_SCALP"
    }
    res = connector.send_trade_request(req)
    assert res["retcode"] == MT5RetCode.TRADE_RETCODE_DONE
    assert res["volume"] == 1.5
    assert "ticket" in connector.get_open_positions()[0]

    # Check open positions
    open_pos = connector.get_open_positions(symbol="XAUUSD")
    assert len(open_pos) == 1
    ticket = open_pos[0]["ticket"]

    # Close position
    closed = connector.close_position(ticket)
    assert closed is True
    assert len(connector.get_open_positions()) == 0


# ---------------------------------------------------------
# 7. The Fourth Estate TCA Slippage Monitor Tests
# ---------------------------------------------------------

def test_tca_slippage_monitor():
    """
    Test TCAMonitor detecting slippage drag and raising SlippageAnomalyAlert on excessive broker widening.
    """
    tca = TCAMonitor(max_allowed_slippage_bps=15.0)

    # 1. Normal fill: BUY at 2000.20 vs theoretical 2000.00 (slippage = 0.20 / 2000 = 1.0 bps <= 15 bps)
    record1 = tca.audit_execution_fill(
        theoretical_price=2000.0,
        fill_price=2000.20,
        action="BUY",
        asset="XAUUSD",
        lots=1.0
    )
    assert record1["slippage_bps"] == 1.0
    assert record1["is_anomaly"] is False

    # 2. Anomalous fill: BUY at 2004.00 vs theoretical 2000.00 (slippage = 4.0 / 2000 = 20.0 bps > 15 bps)
    with pytest.raises(SlippageAnomalyAlert) as exc_info:
        tca.audit_execution_fill(
            theoretical_price=2000.0,
            fill_price=2004.00,
            action="BUY",
            asset="XAUUSD",
            lots=2.0
        )
    assert "TCA WATCHDOG ALERT" in str(exc_info.value)
    assert tca.anomalies_count == 1

    # 3. Telemetry summary
    report = tca.get_tca_telemetry_report()
    assert report["total_fills"] == 2
    assert report["anomalies_count"] == 1
    assert report["broker_health"] == "SLIPPAGE_WARNING"
