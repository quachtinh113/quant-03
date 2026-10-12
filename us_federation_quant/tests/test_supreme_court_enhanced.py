"""
Unit tests for Enhanced Supreme Court (The Judicial Branch - Option A).
Tests:
1. Blind Out-of-Sample Trial with Immutable Trial Counter N & DSR/PSR metrics.
2. 5 Category-5 Black Swan Catastrophic Stress Scenarios.
3. Factor Neutrality Judicial Injunction (Gilbert Strang MIT 18.065).
4. Cryptographic HMAC-SHA256 Warrant Generation & Tamper Resistance.
5. End-to-End Judicial Adjudication with Executive Router handoff.
"""

import importlib
import numpy as np
import pandas as pd
import pytest

_court_mod = importlib.import_module("us_federation_quant.02_supreme_court")
SupremeCourt = _court_mod.SupremeCourt
JudicialReview = _court_mod.JudicialReview
JudicialWarrant = _court_mod.JudicialWarrant
JudicialVetoError = _court_mod.JudicialVetoError
BlackSwanStressTester = _court_mod.BlackSwanStressTester

_bills_mod = importlib.import_module("us_federation_quant.01_congress_alpha.legislative_bills.bill_builder")
Congress = _bills_mod.Congress
AlphaBill = _bills_mod.AlphaBill

_router_mod = importlib.import_module("us_federation_quant.03_executive_presidency.order_router.router")
ExecutiveOrderRouter = _router_mod.ExecutiveOrderRouter
ExecutiveUnauthorizedError = _router_mod.ExecutiveUnauthorizedError

_mit_mod = importlib.import_module("us_federation_quant.01_congress_alpha.mit_dalio_foundation")
MITMatrixCompensator = _mit_mod.MITMatrixCompensator


# ---------------------------------------------------------
# 1. Tests for 5 Category-5 Black Swan Stress Scenarios
# ---------------------------------------------------------

def test_5_category_5_black_swan_crises():
    """Verify all 5 historical financial disaster scenarios run and enforce 7.5% DD ceiling."""
    stress_tester = BlackSwanStressTester()

    # Create dummy bill
    dummy_bill = AlphaBill(
        bill_id="BILL-TEST-BLACK-SWAN",
        target_asset="XAUUSD",
        action="BUY",
        target_lots=5.0,
        house_yes_votes=400,
        senate_yes_votes=90,
        micro_score=0.8,
        variance_ratio=1.4,
        regime="MOMENTUM_TREND",
        timestamp=1000.0,
        passed_bicameral=True
    )

    report = stress_tester.run_all_stress_scenarios(dummy_bill, stop_loss_pct=0.03)

    assert "all_passed" in report
    assert report["total_scenarios"] == 5
    assert "COVID_19_VOLATILITY_SPIKE" in report["scenarios"]
    assert "LIQUIDITY_FREEZE_CRASH" in report["scenarios"]
    assert "SPREAD_EXPLOSION_FLASH_CRASH" in report["scenarios"]
    assert "FED_HAWKISH_RATE_SHOCK" in report["scenarios"]
    assert "CORRELATION_BREAKDOWN_CRASH" in report["scenarios"]

    # Each scenario must verify max drawdown <= 7.5%
    for name, sc in report["scenarios"].items():
        assert sc["max_drawdown"] <= 0.075


# ---------------------------------------------------------
# 2. Tests for Factor Neutrality Judicial Injunction
# ---------------------------------------------------------

def test_factor_neutrality_judicial_injunction():
    """Verify Supreme Court enjoins/vetoes bills with systematic factor leakage."""
    court = SupremeCourt()

    dummy_bill = AlphaBill(
        bill_id="BILL-FACTOR-TEST",
        target_asset="XAUUSD",
        action="BUY",
        target_lots=5.0,
        house_yes_votes=400,
        senate_yes_votes=90,
        micro_score=0.8,
        variance_ratio=1.4,
        regime="MOMENTUM_TREND",
        timestamp=1000.0,
        passed_bicameral=True
    )

    n_assets = 4
    n_factors = 2
    np.random.seed(42)
    B = np.random.randn(n_assets, n_factors)

    # 1. Unhedged weights with strong factor leakage (Must trigger Judicial Veto)
    w_leaking = np.array([0.5, 0.5, 0.5, 0.5])
    with pytest.raises(JudicialVetoError) as exc_info:
        court.adjudicate_bill(
            bill=dummy_bill,
            factor_matrix=B,
            strategy_weights=w_leaking
        )
    assert "FACTOR_LEAKAGE" in str(exc_info.value)

    # 2. Neutralized weights via Strang Nullspace (Must pass injunction check)
    w_clean = MITMatrixCompensator.orthogonal_nullspace_projection(w_leaking, B)
    warrant = court.adjudicate_bill(
        bill=dummy_bill,
        factor_matrix=B,
        strategy_weights=w_clean
    )
    assert warrant.factor_neutrality_verified is True


# ---------------------------------------------------------
# 3. Tests for Cryptographic HMAC-SHA256 Warrant & Tamper Resistance
# ---------------------------------------------------------

def test_cryptographic_warrant_hmac_tamper_resistance():
    """Verify HMAC-SHA256 signature detects any unauthorized tampering of lot size or asset."""
    court = SupremeCourt(secret_key="TOP_SECRET_SCOTUS_KEY")
    router = ExecutiveOrderRouter(secret_key="TOP_SECRET_SCOTUS_KEY")

    dummy_bill = AlphaBill(
        bill_id="BILL-AUTH-001",
        target_asset="XAUUSD",
        action="BUY",
        target_lots=3.5,
        house_yes_votes=380,
        senate_yes_votes=85,
        micro_score=0.75,
        variance_ratio=1.35,
        regime="MOMENTUM_TREND",
        timestamp=2000.0,
        passed_bicameral=True
    )

    # Legitimate adjudication
    warrant = court.adjudicate_bill(dummy_bill, max_lots=3.5)
    assert warrant.verify_token("TOP_SECRET_SCOTUS_KEY") is True

    # Executive router accepts genuine warrant
    micro_orders = router.route_execution(warrant=warrant, market_mid_price=2000.0)
    assert len(micro_orders) > 0

    # Attacker attempts to tamper with authorized lots (e.g. boost from 3.5 to 35.0 lots)
    warrant.authorized_lots = 35.0
    assert warrant.verify_token("TOP_SECRET_SCOTUS_KEY") is False

    # Executive router must REJECT tampered warrant with ExecutiveUnauthorizedError
    with pytest.raises(ExecutiveUnauthorizedError) as exc_info:
        router.route_execution(warrant=warrant, market_mid_price=2000.0)
    assert "UNCONSTITUTIONAL ATTEMPT" in str(exc_info.value)


# ---------------------------------------------------------
# 4. Tests for End-to-End Judicial Review with All 5 Black Swans
# ---------------------------------------------------------

def test_supreme_court_full_adjudication_with_all_black_swans():
    """Verify complete adjudication lifecycle with Black Swan stress testing enforced."""
    court = SupremeCourt()

    np.random.seed(888)
    n = 200
    rets = np.random.normal(0.001, 0.004, n)
    p = 2000.0 * np.exp(np.cumsum(rets))
    market_df = pd.DataFrame({
        "open": p * 0.999,
        "high": p * 1.002,
        "low": p * 0.998,
        "close": p,
        "returns": rets,
        "volume": np.random.uniform(3000, 9000, n)
    })

    # 1. Congress deliberates
    bill = Congress.deliberate_and_vote("XAUUSD", market_df, proposed_lots=4.0)

    # 2. Supreme Court adjudicates with Black Swan requirement enabled
    warrant = court.adjudicate_bill(
        bill=bill,
        max_lots=4.0,
        require_black_swan_pass=True
    )

    assert isinstance(warrant, JudicialWarrant)
    assert warrant.target_asset == "XAUUSD"
    assert warrant.black_swan_scenarios_passed == 5
    assert warrant.dsr >= 0.90
    assert warrant.max_drawdown <= 0.075
    assert warrant.authorized_lots <= 4.0
