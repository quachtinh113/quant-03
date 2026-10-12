"""
Unit Tests for The Fourth Estate & Central Risk Desk (Article VI).
Verifies:
1. Parametric, Historical, and Monte Carlo VaR / CVaR.
2. Market Neutrality (|beta| <= 0.05), Gross Leverage, and HHI.
3. Fourth Estate Slippage Watchdog and Anomaly Alerts.
4. Federal Master Kill-Switch Drawdown Ladder (-3%, -5%, -7.5%) and Cryptographic Unlock.
5. Full Central Risk Desk 360-degree audit and Federation Hub Pre-Trade clearance.
"""

import importlib
import pytest
import numpy as np
import pandas as pd

_fe_mod = importlib.import_module("us_federation_quant.06_the_fourth_estate")
CentralVaREngine = _fe_mod.CentralVaREngine
VaRMetricResult = _fe_mod.VaRMetricResult
ExposureAndBetaDesk = _fe_mod.ExposureAndBetaDesk
ExposureAndBetaReport = _fe_mod.ExposureAndBetaReport
PositionSnapshot = _fe_mod.PositionSnapshot
FourthEstateWatchdog = _fe_mod.FourthEstateWatchdog
SlippageAnomalyAlert = _fe_mod.SlippageAnomalyAlert
FederalMasterKillSwitch = _fe_mod.FederalMasterKillSwitch
FederalCircuitBreakerActive = _fe_mod.FederalCircuitBreakerActive
CentralRiskDesk = _fe_mod.CentralRiskDesk
CentralRiskAuditReport = _fe_mod.CentralRiskAuditReport

from us_federation_quant.federation_hub import FederationHub


def test_parametric_var():
    """Test parametric VaR under known weights and covariance."""
    engine = CentralVaREngine(default_confidence=0.99)
    weights = np.array([0.5, 0.5])
    cov = np.array([
        [0.0004, 0.0001],
        [0.0001, 0.0004]
    ])
    equity = 1_000_000.0

    res = engine.calculate_parametric_var(weights, cov, equity, confidence_level=0.99)
    assert res["var_pct"] > 0
    assert res["var_dollar"] > 0
    # For z_0.99 ~= 2.326, sigma = sqrt(0.5^2*0.0004*2 + 2*0.25*0.0001) = sqrt(0.0002 + 0.00005) = sqrt(0.00025) ~= 0.0158
    assert 0.01 < res["var_pct"] < 0.06
    assert 10_000 < res["var_dollar"] < 60_000


def test_historical_var_and_cvar():
    """Test historical simulation VaR and Expected Shortfall (CVaR)."""
    engine = CentralVaREngine()
    np.random.seed(42)
    # Generate 500 daily returns with some negative tail
    hist_returns = np.random.normal(0.0005, 0.015, (500, 2))
    weights = np.array([0.6, 0.4])
    equity = 500_000.0

    res = engine.calculate_historical_var_cvar(hist_returns, weights, equity, confidence_level=0.99)
    assert res["var_pct"] > 0
    assert res["cvar_pct"] >= res["var_pct"]  # Expected Shortfall must be >= VaR
    assert res["cvar_dollar"] >= res["var_dollar"]


def test_monte_carlo_var_cvar():
    """Test Monte Carlo simulation with 5,000 draws."""
    engine = CentralVaREngine()
    weights = np.array([0.7, 0.3])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0003]])
    equity = 1_000_000.0

    res = engine.calculate_monte_carlo_var_cvar(
        weights=weights,
        cov_matrix=cov,
        mean_returns=None,
        portfolio_equity=equity,
        num_simulations=5000,
        confidence_level=0.99
    )
    assert res["var_pct"] > 0
    assert res["cvar_pct"] >= res["var_pct"]
    assert res["num_simulations"] == 5000


def test_exposure_and_beta_desk_neutrality():
    """Test Exposure and Beta desk enforcing institutional Market Neutrality (|beta| <= 0.05)."""
    desk = ExposureAndBetaDesk(max_market_beta=0.05, max_gross_leverage=3.0)
    equity = 1_000_000.0

    # 1. Market Neutral Portfolio (4 assets diversified, HHI = 0.25 <= 0.35, Single Asset = 25% <= 40%)
    # Beta_port = (250k/1M)*0.20 + (-250k/1M)*0.20 + (250k/1M)*0.10 + (-250k/1M)*0.10 = 0.0
    neutral_positions = [
        PositionSnapshot(asset="XAUUSD", notional_value=250_000.0, asset_beta=0.20),
        PositionSnapshot(asset="GOLD_PROXY", notional_value=-250_000.0, asset_beta=0.20),
        PositionSnapshot(asset="US30", notional_value=250_000.0, asset_beta=0.10),
        PositionSnapshot(asset="INDEX_HEDGE", notional_value=-250_000.0, asset_beta=0.10)
    ]
    report_neutral = desk.audit_positions(neutral_positions, equity)
    assert report_neutral.is_compliant
    assert report_neutral.is_market_neutral
    assert abs(report_neutral.portfolio_market_beta) < 1e-4
    assert report_neutral.gross_leverage == 1.0
    assert report_neutral.hhi_concentration <= 0.35

    # 2. Aggressive Directional Portfolio violating Beta and Leverage
    # Gross = 4.0M on 1M equity = 4.0x leverage (exceeds limit 3.0x), Beta = 4.0 * 1.2 = 4.8
    unhedged_positions = [
        PositionSnapshot(asset="US30", notional_value=4_000_000.0, asset_beta=1.20)
    ]
    report_unhedged = desk.audit_positions(unhedged_positions, equity)
    assert not report_unhedged.is_compliant
    assert not report_unhedged.is_market_neutral
    assert any("Beta" in v for v in report_unhedged.violations)
    assert any("Gross leverage" in v for v in report_unhedged.violations)


def test_fourth_estate_slippage_watchdog():
    """Test Fourth Estate independent watchdog telemetry and anomaly alert."""
    watchdog = FourthEstateWatchdog(max_allowed_slippage_bps=10.0)

    # 1. Clean fill (Slippage: 2000.50 vs 2000.00 = +2.5 bps)
    record = watchdog.audit_fill(
        theoretical_price=2000.0,
        fill_price=2000.50,
        action="BUY",
        asset="XAUUSD"
    )
    assert not record.is_anomaly
    assert record.slippage_bps == 2.50

    # 2. Compromised fill triggering SlippageAnomalyAlert (Slippage: 2003.00 vs 2000.00 = +15 bps)
    with pytest.raises(SlippageAnomalyAlert):
        watchdog.audit_fill(
            theoretical_price=2000.0,
            fill_price=2003.00,
            action="BUY",
            asset="XAUUSD"
        )

    # 3. Publish risk dispatch
    dispatch = watchdog.publish_risk_dispatch()
    assert dispatch.total_fills_audited == 2
    assert dispatch.anomalies_detected == 1


def test_federal_master_kill_switch_ladder():
    """Test Federal Master Kill-Switch totalitarian drawdown ladder and unlock."""
    ks = FederalMasterKillSwitch(
        yellow_threshold=-0.03,
        orange_threshold=-0.05,
        red_threshold=-0.075,
        secret_passphrase="TOP_SECRET_PASSKEY"
    )

    # Peak: $1,000,000
    dir_normal = ks.update_equity(1_000_000.0)
    assert dir_normal.status_level == "NORMAL"
    assert dir_normal.position_scale_factor == 1.0

    # Level 1: Drawdown -3.5% ($965,000) -> YELLOW ALERT
    dir_yellow = ks.update_equity(965_000.0)
    assert dir_yellow.status_level == "YELLOW_ALERT"
    assert dir_yellow.position_scale_factor == 0.50
    assert not dir_yellow.is_trading_locked

    # Level 2: Drawdown -5.5% ($945,000) -> ORANGE ALERT
    dir_orange = ks.update_equity(945_000.0)
    assert dir_orange.status_level == "ORANGE_ALERT"
    assert dir_orange.position_scale_factor == 0.25
    assert not dir_orange.is_trading_locked

    # Level 3: Drawdown -8.0% ($920,000) -> RED KILL-SWITCH
    dir_red = ks.update_equity(920_000.0)
    assert dir_red.status_level == "RED_KILL_SWITCH"
    assert dir_red.is_trading_locked
    assert dir_red.position_scale_factor == 0.0

    # Verify orders are blocked
    with pytest.raises(FederalCircuitBreakerActive):
        ks.verify_order_permission()

    # Attempt unlock with wrong key -> FAILS
    assert not ks.unlock_federation("WRONG_KEY")
    assert ks.is_locked

    # Unlock with constitutional passkey -> SUCCESS
    assert ks.unlock_federation("TOP_SECRET_PASSKEY")
    assert not ks.is_locked
    # Now order permission passes
    ks.verify_order_permission()


def test_central_risk_desk_full_audit():
    """Test comprehensive 360-degree Central Risk Desk audit."""
    crd = CentralRiskDesk()
    equity = 1_000_000.0
    positions = [
        PositionSnapshot(asset="XAUUSD", notional_value=200_000.0, asset_beta=0.05),
        PositionSnapshot(asset="US30", notional_value=-150_000.0, asset_beta=0.06)
    ]
    weights = np.array([0.6, 0.4])
    cov = np.array([[0.0004, 0.0001], [0.0001, 0.0003]])
    hist_returns = np.random.normal(0.0005, 0.015, (250, 2))

    report = crd.audit_entire_federation(
        portfolio_equity=equity,
        positions=positions,
        historical_returns=hist_returns,
        asset_weights=weights,
        cov_matrix=cov
    )

    assert report.overall_status in ["APPROVED", "CAUTION_WARNING"]
    assert report.is_approved_for_trading
    assert report.var_metrics is not None
    assert report.var_metrics.parametric_var_pct > 0
    assert report.exposure_report.gross_leverage > 0


def test_federation_hub_integrated_risk_veto():
    """Test FederationHub halts execution when Central Risk Desk Kill-Switch is engaged."""
    hub = FederationHub()
    bars = 30
    close = 2000.0 + np.cumsum(np.random.randn(bars) * 2.0)
    df = pd.DataFrame({
        "open": close - 1,
        "high": close + 3,
        "low": close - 3,
        "close": close,
        "volume": np.full(bars, 1000.0)
    })

    # Trigger emergency kill-switch manually on central risk desk
    hub.central_risk_desk.kill_switch.manual_emergency_shutdown("Simulated Central Risk Stress")

    # Order lifecycle should be intercepted and vetoed by central risk desk
    res = hub.process_order_lifecycle(
        asset="XAUUSD",
        market_data_df=df,
        proposed_lots=3.0,
        current_volatility=0.012
    )
    assert res["status"] == "VETOED_BY_CENTRAL_RISK_DESK"
    assert "Master Kill-Switch is ACTIVE" in res["reason"]
