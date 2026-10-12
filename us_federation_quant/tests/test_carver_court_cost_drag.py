"""
========================================================================================
Unit Tests for Robert Carver Cost-to-Sharpe Drag Filter in Supreme Court (Pha 3)
========================================================================================
"""

import pytest
import numpy as np
import pandas as pd
import importlib

_review_mod = importlib.import_module("us_federation_quant.02_supreme_court.judicial_review")
JudicialReview = _review_mod.JudicialReview

_court_mod = importlib.import_module("us_federation_quant.02_supreme_court.cryptographic_warrant")
SupremeCourt = _court_mod.SupremeCourt
JudicialVetoError = _court_mod.JudicialVetoError


class MockAlphaBill:
    bill_id = "BILL-COST-AUDIT-TEST"
    target_asset = "XAUUSDm"
    action = "BUY"
    proposed_lots = 1.0
    is_fracdiff_stationary = True
    meta_win_probability = 0.65


def test_judicial_review_carver_cost_drag_passes_healthy_strategy():
    reviewer = JudicialReview()
    bill = MockAlphaBill()

    # Normal institutional strategy: low spread (2 bps), low turnover (10x/yr)
    # Gross SR is ~3.0, cost drag is negligible
    audit = reviewer.audit_bill(
        bill=bill,
        num_trials=5,
        spread_bps=2.0,
        turnover_per_year=10.0,
        annual_vol_pct=16.0,
        max_cost_drag_ratio=0.50,
        min_net_sr=0.20,
    )

    assert audit["carver_cost_audit_passed"] is True
    assert audit["cost_drag_sr"] < 0.05
    assert audit["annualized_net_sr"] > 0.50
    assert audit["cost_drag_ratio"] < 0.10


def test_judicial_review_carver_cost_drag_rejects_churn_strategy():
    reviewer = JudicialReview()
    bill = MockAlphaBill()

    # Hyperactive churn strategy: high spread (25 bps) and extreme turnover (300x/yr)
    # Cost drag = (0.0025 * 300) / 0.16 = 0.75 / 0.16 = 4.68 SR points!
    # Even with Gross SR = 2.0, Net SR becomes negative (-2.68 SR)
    audit = reviewer.audit_bill(
        bill=bill,
        num_trials=5,
        spread_bps=25.0,
        turnover_per_year=300.0,
        annual_vol_pct=16.0,
        max_cost_drag_ratio=0.50,
        min_net_sr=0.20,
    )

    assert audit["carver_cost_audit_passed"] is False
    assert audit["pass_audit"] is False
    assert any("CARVER_COST_DRAG_EXCESSIVE" in r for r in audit["rejection_reasons"])


def test_supreme_court_vetoes_cost_excessive_bill():
    court = SupremeCourt(secret_key="TEST_SEAL")
    bill = MockAlphaBill()

    # Patch reviewer.audit_bill or pass excessive turnover
    with pytest.raises(JudicialVetoError) as exc_info:
        # Create a judicial review that fails cost audit
        court.reviewer.audit_bill = lambda *args, **kwargs: {
            "bill_id": bill.bill_id,
            "pass_audit": False,
            "rejection_reasons": ["CARVER_COST_DRAG_EXCESSIVE_RATIO_85.2%_NET_SR_0.12"],
        }
        court.adjudicate_bill(bill)

    assert "CARVER_COST_DRAG_EXCESSIVE" in str(exc_info.value)
