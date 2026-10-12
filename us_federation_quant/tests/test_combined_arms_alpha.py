"""
Unit Tests for Combined Arms Alpha Tactical Warfare Engine (Tác Chiến Binh Chủng Hợp Thành)
Validates:
1. Reconnaissance Unit (Trinh Sát Vi Mô)
2. Armored Momentum Unit (Thiết Giáp Đột Kích)
3. Artillery Mean Reversion Unit (Pháo Binh Chế Áp)
4. Air Defense Volatility Unit (Phòng Không Đánh Chặn)
5. Joint Command Matrix (Bộ Tổng Tham Mưu Hợp Thành)
"""

import pytest
import numpy as np
import pandas as pd
import importlib

_mod = importlib.import_module("us_federation_quant.01_congress_alpha.combined_arms_alpha")
ReconnaissanceUnit = _mod.ReconnaissanceUnit
ArmoredMomentumUnit = _mod.ArmoredMomentumUnit
ArtilleryMeanReversionUnit = _mod.ArtilleryMeanReversionUnit
AirDefenseVolatilityUnit = _mod.AirDefenseVolatilityUnit
CombinedArmsCommander = _mod.CombinedArmsCommander
CombinedArmsDirective = _mod.CombinedArmsDirective


@pytest.fixture
def trending_market_data():
    """Generates strong momentum trending market data with positive autocorrelation."""
    np.random.seed(42)
    n = 150
    returns = []
    r = 0.002
    for _ in range(n):
        r = 0.5 * r + np.random.normal(0.001, 0.003)
        returns.append(r)
    price = 2000.0 * np.exp(np.cumsum(returns))
    return pd.DataFrame({
        "open": np.roll(price, 1),
        "high": price * 1.002,
        "low": price * 0.998,
        "close": price,
        "volume": np.random.uniform(2000, 6000, n)
    })


@pytest.fixture
def ranging_market_data():
    """Generates pure Ornstein-Uhlenbeck mean-reverting market data (Ideal for Artillery)."""
    np.random.seed(99)
    n = 150
    x = 0.0
    prices = []
    for _ in range(n):
        dx = -0.6 * x + np.random.normal(0, 0.8)
        x += dx
        prices.append(2000.0 + x)
    price = np.array(prices)
    return pd.DataFrame({
        "open": np.roll(price, 1),
        "high": price + 0.5,
        "low": price - 0.5,
        "close": price,
        "volume": np.random.uniform(1000, 3000, n)
    })


def test_reconnaissance_unit_intel(trending_market_data):
    """Test 1: Reconnaissance unit scans micro-features and flow imbalance."""
    report = ReconnaissanceUnit.scan_market(trending_market_data)
    assert report["unit"] == "RECON_INTEL_UNIT"
    assert -1.0 <= report["recon_score"] <= 1.0
    assert 0.0 <= report["confidence"] <= 1.0
    assert "alpha_6_stealth" in report["intel"]


def test_armored_momentum_assault(trending_market_data):
    """Test 2: Armored Momentum unit charges strongly during upward trend."""
    report = ArmoredMomentumUnit.launch_assault(trending_market_data)
    assert report["unit"] == "ARMORED_MOMENTUM_UNIT"
    assert report["firepower"] > 0.0
    assert report["metrics"]["ema_alignment"] == 1.0


def test_artillery_mean_reversion_barrage(ranging_market_data):
    """Test 3: Artillery unit fires barrage when price stretches away from mean."""
    report = ArtilleryMeanReversionUnit.fire_barrage(ranging_market_data)
    assert report["unit"] == "ARTILLERY_FIRE_UNIT"
    assert -1.0 <= report["barrage_power"] <= 1.0
    assert isinstance(report["firing"], bool)


def test_air_defense_shield_radar(trending_market_data):
    """Test 4: Air defense unit monitors airspace and calculates defense multiplier."""
    report = AirDefenseVolatilityUnit.scan_airspace(trending_market_data)
    assert report["unit"] == "AIR_DEFENSE_SHIELD"
    assert 0.0 < report["defense_multiplier"] <= 1.0
    assert "threat_level" in report


def test_joint_command_matrix_directive_on_trending_market(trending_market_data):
    """Test 5: Combined Arms Commander deploys Armored Cavalry as primary branch on trending terrain."""
    directive = CombinedArmsCommander.execute_tactical_assessment(
        asset="XAUUSD",
        market_df=trending_market_data,
        base_lots=5.0
    )

    assert isinstance(directive, CombinedArmsDirective)
    assert directive.target_asset == "XAUUSD"
    assert directive.action in ["BUY", "HOLD"]
    assert directive.primary_branch == "ARMORED_CAVALRY_MOMENTUM"
    assert directive.tactical_breakdown["branch_weights"]["w_armor"] == 0.65


def test_joint_command_matrix_directive_on_ranging_market(ranging_market_data):
    """Test 6: Combined Arms Commander shifts primary weight to Artillery on ranging terrain."""
    directive = CombinedArmsCommander.execute_tactical_assessment(
        asset="XAUUSD",
        market_df=ranging_market_data,
        base_lots=5.0
    )

    assert isinstance(directive, CombinedArmsDirective)
    assert directive.tactical_breakdown["terrain"] == "MEAN_REVERSION_TERRAIN"
    assert directive.primary_branch == "ARTILLERY_FIRE_SUPPRESSION"
    assert directive.tactical_breakdown["branch_weights"]["w_artillery"] == 0.70
