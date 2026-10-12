"""
========================================================================================
Unit Tests for Robert Carver (pysystemtrade) Portfolio Engine Integration
in Federal Reserve Dynamic QE/QT Allocator (Giai đoạn 2)
========================================================================================
"""

import pytest
import numpy as np
import pandas as pd
import importlib

_fed_mod = importlib.import_module("us_federation_quant.04_federal_reserve.dynamic_qe_qt_allocator")
FederalReserveAllocator = _fed_mod.FederalReserveAllocator
CarverQEAllocationEngine = _fed_mod.CarverQEAllocationEngine


# --------------------------------------------------------------------------------------
# 1. Carver Policy Volatility Target & Sizing Tests
# --------------------------------------------------------------------------------------

def test_carver_engine_policy_adjusted_vol_target():
    engine = CarverQEAllocationEngine(base_annual_target_vol_pct=16.0)

    # QE: Aggressive expansion during calm regimes
    assert engine.get_policy_adjusted_vol_target("QE_QUANTITATIVE_EASING") == 20.0

    # Neutral: Man AHL / Carver standard benchmark
    assert engine.get_policy_adjusted_vol_target("NEUTRAL") == 16.0

    # QT: Strong capital defense during violent volatility
    assert engine.get_policy_adjusted_vol_target("QT_QUANTITATIVE_TIGHTENING") == 8.0


def test_carver_idm_bounds_and_matrix_scaling():
    engine = CarverQEAllocationEngine()

    # Case A: 5 Completely Uncorrelated Assets (Identity Matrix)
    cov_uncorrelated = np.eye(5) * 0.0004
    idm_uncorr, corr_uncorr = engine.compute_idm_from_covariance(cov_uncorrelated)
    assert 1.0 <= idm_uncorr <= 2.5
    # For 5 equal uncorrelated assets: 1/sqrt(5 * (1/25)) = sqrt(5) ~ 2.236
    assert np.isclose(idm_uncorr, np.sqrt(5), atol=0.05)

    # Case B: 5 Perfectly Correlated Assets (All 1.0)
    cov_correlated = np.ones((5, 5)) * 0.0004
    idm_corr, corr_corr = engine.compute_idm_from_covariance(cov_correlated)
    assert np.isclose(idm_corr, 1.0, atol=0.01)

    # Case C: 1 Asset -> IDM must be 1.0
    idm_single, _ = engine.compute_idm_from_covariance(np.array([[0.0004]]))
    assert idm_single == 1.0


def test_carver_position_buffering():
    engine = CarverQEAllocationEngine(buffer_fraction=0.10)  # 10% trade buffer

    # Target within 5% of current position -> Buffer active (keep current value)
    current_val = 100_000.0
    target_val = 104_000.0  # +4% change
    buffered_val, was_buffered = engine.apply_position_buffer(current_val, target_val)
    assert was_buffered is True
    assert buffered_val == 100_000.0

    # Target outside 10% -> Buffer inactive (accept new target)
    target_val_large = 115_000.0  # +15% change
    buffered_val_large, was_buffered_large = engine.apply_position_buffer(current_val, target_val_large)
    assert was_buffered_large is False
    assert buffered_val_large == 115_000.0

    # If current position is zero -> Buffer never triggers
    zero_val, was_zero_buffered = engine.apply_position_buffer(0.0, 50_000.0)
    assert was_zero_buffered is False
    assert zero_val == 50_000.0


# --------------------------------------------------------------------------------------
# 2. Federal Reserve Allocator Carver Integration Tests
# --------------------------------------------------------------------------------------

def test_federal_reserve_allocate_carver_quotas_neutral():
    allocator = FederalReserveAllocator(base_total_capital=10_000_000.0)

    # Generate synthetic multi-pod returns
    np.random.seed(42)
    pod_names = ["STATE_01_XAU", "STATE_02_US30", "STATE_05_BTC", "STATE_21_EUR", "STATE_36_AAPL"]
    returns_data = np.random.normal(0.0005, 0.01, (100, 5))
    returns_df = pd.DataFrame(returns_data, columns=pod_names)

    res = allocator.allocate_carver_state_quotas(
        returns_df=returns_df,
        market_volatility=0.012,  # Moderate vol -> NEUTRAL policy
        avg_pod_sharpe=1.8,
        buffer_fraction=0.10,
    )

    assert res["policy"] == "NEUTRAL"
    assert res["quota_multiplier"] == 1.0
    assert res["annual_target_vol_pct"] == 16.0
    assert res["idm"] > 1.0
    assert len(res["quotas"]) == 5
    assert len(res["cash_vol_targets"]) == 5

    # Check cash vol targets positive and non-zero
    for pod in pod_names:
        assert res["quotas"][pod] > 0
        assert res["cash_vol_targets"][pod] > 0


def test_federal_reserve_allocate_carver_quotas_qe_and_qt_scaling():
    allocator = FederalReserveAllocator(base_total_capital=10_000_000.0)
    np.random.seed(123)
    pod_names = ["STATE_01", "STATE_02", "STATE_03"]
    returns_df = pd.DataFrame(np.random.normal(0.001, 0.008, (80, 3)), columns=pod_names)

    # 1. Test QE: Volatility is low (0.008) and Sharpe high (2.2)
    res_qe = allocator.allocate_carver_state_quotas(
        returns_df=returns_df,
        market_volatility=0.008,
        avg_pod_sharpe=2.2,
    )
    assert res_qe["policy"] == "QE_QUANTITATIVE_EASING"
    assert res_qe["quota_multiplier"] == 1.25
    assert res_qe["annual_target_vol_pct"] == 20.0

    # 2. Test QT: Volatility spikes (0.035)
    res_qt = allocator.allocate_carver_state_quotas(
        returns_df=returns_df,
        market_volatility=0.035,
        avg_pod_sharpe=0.5,
    )
    assert res_qt["policy"] == "QT_QUANTITATIVE_TIGHTENING"
    assert res_qt["quota_multiplier"] == 0.5
    assert res_qt["annual_target_vol_pct"] == 8.0

    # Under QT, total allocated capital must be halved compared to neutral baseline
    assert res_qt["total_allocated"] < res_qe["total_allocated"]


def test_federal_reserve_carver_buffering_prevents_churn():
    allocator = FederalReserveAllocator(base_total_capital=1_000_000.0)
    np.random.seed(999)
    pod_names = ["STATE_A", "STATE_B"]
    returns_df = pd.DataFrame(np.random.normal(0.0005, 0.01, (60, 2)), columns=pod_names)

    # First allocation without prior quotas
    res_first = allocator.allocate_carver_state_quotas(returns_df=returns_df)
    first_quotas = res_first["quotas"]
    assert len(res_first["buffered_states"]) == 0

    # Second allocation: provide previous_quotas that are 98% of target (within 10% buffer)
    prev_quotas = {k: v * 0.98 for k, v in first_quotas.items()}
    res_buffered = allocator.allocate_carver_state_quotas(
        returns_df=returns_df,
        previous_quotas=prev_quotas,
        buffer_fraction=0.10,
    )

    # Both states must be buffered to prevent turnover friction
    assert len(res_buffered["buffered_states"]) == 2
    for pod in pod_names:
        assert res_buffered["quotas"][pod] == round(prev_quotas[pod], 2)
