"""
Unit tests for Institutional Formulaic Alpha Fleet & Meta-Labeling Kelly Sizing Engine.
Tests:
1. Marcos López de Prado FracDiff FFD Engine (Weights, ADF stationarity, memory correlation).
2. Zura Kakushadze 101 Formulaic Alphas & Garman-Klass Volatility.
3. Meta-Labeling Secondary Filter & Fractional Kelly Bet Sizing.
4. Congress Alpha Bill Deliberation with FracDiff and Meta-Labeling integration.
"""

import importlib
import numpy as np
import pandas as pd
import pytest

_fleet_mod = importlib.import_module("us_federation_quant.01_congress_alpha.formulaic_alpha_fleet")
FracDiffEngine = _fleet_mod.FracDiffEngine
FracDiffAudit = _fleet_mod.FracDiffAudit
FormulaicAlphas101 = _fleet_mod.FormulaicAlphas101
FormulaicAlphaSnapshot = _fleet_mod.FormulaicAlphaSnapshot
MetaLabelingFilter = _fleet_mod.MetaLabelingFilter
MetaLabelingVerdict = _fleet_mod.MetaLabelingVerdict

_bills_mod = importlib.import_module("us_federation_quant.01_congress_alpha.legislative_bills.bill_builder")
Congress = _bills_mod.Congress
AlphaBill = _bills_mod.AlphaBill


# ---------------------------------------------------------
# 1. Tests for FracDiff Engine
# ---------------------------------------------------------

def test_fracdiff_weights_generation():
    """Verify FFD binomial weights decay and initial terms: w_0 = 1, w_1 = -d."""
    d = 0.4
    weights = FracDiffEngine.get_weights_ffd(d=d, thres=1e-4)
    # The last element of the reversed array is w_0 = 1.0
    assert abs(weights[-1] - 1.0) < 1e-6
    # The second to last element is w_1 = -d = -0.4
    assert abs(weights[-2] - (-0.4)) < 1e-4
    # All earlier weights should decay in absolute value towards threshold
    assert abs(weights[0]) < 1e-2


def test_fracdiff_find_optimal_d_stationarity_and_memory():
    """Verify find_optimal_d discovers stationary d* with ADF p < 0.05 and preserves memory."""
    np.random.seed(42)
    n = 250
    # Geometric Brownian Motion (Non-stationary price series)
    returns = np.random.normal(0.0005, 0.01, n)
    price = pd.Series(100.0 * np.exp(np.cumsum(returns)), name="close")

    audit, stat_series = FracDiffEngine.find_optimal_d(price, step=0.10, p_val_threshold=0.05)

    assert isinstance(audit, FracDiffAudit)
    assert audit.is_stationary is True
    assert audit.p_value < 0.05
    # Optimal d should be less than 1.0 (sub-integer differencing)
    assert 0.0 < audit.optimal_d <= 1.0
    # Memory correlation should be positive and substantial
    assert audit.memory_correlation > 0.40
    assert len(stat_series) > 50


# ---------------------------------------------------------
# 2. Tests for Kakushadze 101 Formulaic Alphas & Microstructure
# ---------------------------------------------------------

def test_kakushadze_formulaic_alphas():
    """Verify calculation of Kakushadze alphas: 001, 006, 012, 054, 101 and GK Volatility."""
    np.random.seed(777)
    n = 100
    p = 150.0 + np.cumsum(np.random.normal(0.05, 0.8, n))
    df = pd.DataFrame({
        "open": p - 0.2,
        "high": p + 1.0,
        "low": p - 1.0,
        "close": p,
        "volume": np.random.uniform(500, 2000, n)
    })

    snap = FormulaicAlphas101.evaluate_alpha_snapshot(df)

    assert isinstance(snap, FormulaicAlphaSnapshot)
    # Composite alpha score must be bounded in [-1.0, 1.0]
    assert -1.0 <= snap.composite_alpha_score <= 1.0
    # Signal strength in [0.0, 1.0]
    assert 0.0 <= snap.signal_strength <= 1.0
    # Garman-Klass volatility must be positive
    assert snap.garman_klass_vol > 0.0
    # Parkinson volatility must be positive
    assert snap.parkinson_vol > 0.0


# ---------------------------------------------------------
# 3. Tests for Meta-Labeling & Fractional Kelly Sizing
# ---------------------------------------------------------

def test_meta_labeling_and_fractional_kelly():
    """Verify Meta-Labeling conviction evaluation and Fractional Kelly sizing."""
    # 1. High conviction trade: Trending market, low volatility, strong signal
    verdict_strong = MetaLabelingFilter.evaluate_conviction_and_size(
        primary_action="BUY",
        signal_strength=0.85,
        market_regime="MOMENTUM_TREND",
        variance_ratio=1.45,
        volatility_gk=0.012,
        fed_liquidity_multiplier=1.2,
        base_lots=5.0
    )

    assert isinstance(verdict_strong, MetaLabelingVerdict)
    assert verdict_strong.is_approved is True
    assert verdict_strong.win_probability >= 0.55
    assert verdict_strong.recommended_lots > 0.0
    assert verdict_strong.fractional_kelly_multiplier > 0.5

    # 2. Hold action must be rejected
    verdict_hold = MetaLabelingFilter.evaluate_conviction_and_size(
        primary_action="HOLD",
        signal_strength=0.0,
        market_regime="RANDOM_WALK",
        variance_ratio=1.0,
        volatility_gk=0.01
    )
    assert verdict_hold.is_approved is False
    assert verdict_hold.recommended_lots == 0.0


# ---------------------------------------------------------
# 4. Tests for Congress Deliberation with FracDiff & Meta-Labeling
# ---------------------------------------------------------

def test_congress_deliberation_institutional_bill():
    """Verify Congress deliberates and produces an AlphaBill with FracDiff & Kelly attributes."""
    np.random.seed(999)
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

    bill = Congress.deliberate_and_vote("XAUUSD", market_df, proposed_lots=5.0)

    assert isinstance(bill, AlphaBill)
    assert bill.target_asset == "XAUUSD"
    assert bill.house_yes_votes > 0
    assert bill.senate_yes_votes > 0
    # Must contain enriched institutional attributes
    assert 0.0 < bill.optimal_d <= 1.0
    assert -1.0 <= bill.composite_alpha_score <= 1.0
    assert 0.0 <= bill.meta_win_probability <= 1.0
    assert bill.target_lots > 0.0
    assert bill.alpha_conviction_summary is not None
