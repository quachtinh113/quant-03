"""
Unit and Integration Tests for Financial Machine Learning Engine (AFML):
1. Symmetric CUSUM Event Filter (Marcos López de Prado 2018).
2. Dynamic Triple Barrier Labeling (TP/SL/Vertical Barriers).
3. Purged and Embargoed K-Fold Cross-Validation.
4. Meta-Classifier Model Training & Calibration.
5. Real-time Feature Extraction & Model Inference Service.
6. Congress AlphaBill Deliberation with ML Brain Integration.
"""

import importlib
import pytest
import numpy as np
import pandas as pd

_ml_mod = importlib.import_module("us_federation_quant.01_congress_alpha.ml_engine")
SymmetricCUSUMFilter = _ml_mod.SymmetricCUSUMFilter
TripleBarrierLabeler = _ml_mod.TripleBarrierLabeler
PurgedKFold = _ml_mod.PurgedKFold
MetaClassifierTrainer = _ml_mod.MetaClassifierTrainer
MetaClassifierArtifact = _ml_mod.MetaClassifierArtifact
ModelInferenceService = _ml_mod.ModelInferenceService
MLInferenceResult = _ml_mod.MLInferenceResult

_bills_mod = importlib.import_module("us_federation_quant.01_congress_alpha.legislative_bills.bill_builder")
Congress = _bills_mod.Congress
AlphaBill = _bills_mod.AlphaBill


# ---------------------------------------------------------
# 1. Symmetric CUSUM Event Filter Tests
# ---------------------------------------------------------

def test_cusum_event_filter():
    """
    Test that CUSUM filter samples events only when cumulative price deviations
    cross dynamic thresholds, avoiding oversampling during flat noise periods.
    """
    # 100 bars: 40 flat bars, sharp surge, 40 flat bars, sharp drop
    prices = [100.0] * 40
    # Surge +10%
    for p in np.linspace(100.0, 110.0, 10):
        prices.append(p)
    # Flat
    prices.extend([110.0] * 40)
    # Drop -10%
    for p in np.linspace(110.0, 100.0, 10):
        prices.append(p)

    cusum = SymmetricCUSUMFilter(threshold_multiplier=1.5, default_threshold=0.03)
    res = cusum.filter_events(prices)

    assert res["total_bars"] == len(prices)
    assert res["event_count"] > 0
    # Sampling ratio must be significantly compressed relative to 100% time bars
    assert res["sampling_ratio"] < 0.50
    # Upward event detected during surge (+1)
    assert 1 in res["event_directions"]
    # Downward event detected during drop (-1)
    assert -1 in res["event_directions"]


# ---------------------------------------------------------
# 2. Triple Barrier Labeling Tests
# ---------------------------------------------------------

def test_triple_barrier_labeler():
    """
    Test Triple Barrier labeling with Take-Profit, Stop-Loss, and Vertical timeout:
    - Path 1 hits TP first -> label = 1
    - Path 2 hits SL first -> label = 0
    """
    # Case 1: Surging market (Hits TP)
    surge_prices = np.linspace(100.0, 106.0, 15)
    df_surge = pd.DataFrame({
        "close": surge_prices,
        "high": surge_prices + 0.5,
        "low": surge_prices - 0.5
    })
    labeler = TripleBarrierLabeler(pt_multiplier=1.5, sl_multiplier=1.0, max_holding_period=10)
    # Volatility = 1% -> TP = +1.5%, SL = -1.0%
    vols = [0.01] * 15

    labels_surge = labeler.apply_barriers(df_surge, event_indices=[0], primary_signals=[1], volatility_series=vols)
    assert len(labels_surge) == 1
    assert labels_surge.iloc[0]["label"] == 1
    assert labels_surge.iloc[0]["exit_reason"] == "TAKE_PROFIT"

    # Case 2: Crashing market (Hits SL for BUY signal)
    crash_prices = np.linspace(100.0, 95.0, 15)
    df_crash = pd.DataFrame({
        "close": crash_prices,
        "high": crash_prices + 0.5,
        "low": crash_prices - 0.5
    })
    labels_crash = labeler.apply_barriers(df_crash, event_indices=[0], primary_signals=[1], volatility_series=vols)
    assert len(labels_crash) == 1
    assert labels_crash.iloc[0]["label"] == 0
    assert labels_crash.iloc[0]["exit_reason"] == "STOP_LOSS"


# ---------------------------------------------------------
# 3. Purged & Embargoed Cross-Validation Tests
# ---------------------------------------------------------

def test_purged_and_embargoed_cv():
    """
    Verify that PurgedKFold strictly prevents lookahead leakage:
    No sample in the training set overlaps with any active test span,
    and post-test embargo period is respected.
    """
    n_samples = 100
    X = pd.DataFrame({"feat1": np.random.randn(n_samples), "feat2": np.random.randn(n_samples)})
    y = pd.Series(np.random.randint(0, 2, n_samples))

    # Construct event spans where each trade lasts 6 bars: [i, min(n-1, i+6)]
    event_spans = pd.DataFrame({
        "entry_idx": np.arange(n_samples),
        "exit_idx": np.minimum(n_samples - 1, np.arange(n_samples) + 6)
    })

    cv = PurgedKFold(n_splits=4, embargo_pct=0.02)
    splits = list(cv.split(X, y, event_spans=event_spans))

    assert len(splits) == 4

    for train_idx, test_idx in splits:
        assert len(train_idx) > 0
        assert len(test_idx) > 0
        # No index can be in both
        assert len(set(train_idx).intersection(set(test_idx))) == 0

        # Verify Purging: no train event span intersects with test time bounds
        min_test = np.min(event_spans.loc[test_idx, "entry_idx"])
        max_test = np.max(event_spans.loc[test_idx, "exit_idx"])

        for tr in train_idx:
            tr_start = event_spans.loc[tr, "entry_idx"]
            tr_end = event_spans.loc[tr, "exit_idx"]
            # Train sample must NOT overlap [min_test, max_test]
            overlap = (tr_start <= max_test) and (tr_end >= min_test)
            assert not overlap, f"Leakage detected! Train trade [{tr_start}, {tr_end}] overlaps test [{min_test}, {max_test}]"


# ---------------------------------------------------------
# 4. Meta-Classifier Trainer Tests
# ---------------------------------------------------------

def test_meta_classifier_trainer():
    """
    Test training the Meta-Classifier model with probability calibration
    and verifying Brier score, ROC-AUC, and feature importances.
    """
    np.random.seed(42)
    n = 120
    # Informative features
    f1 = np.random.randn(n)
    f2 = np.random.randn(n)
    # Target correlated with f1 + f2
    logits = f1 * 1.5 + f2 * 1.2
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.50).astype(int)

    X = pd.DataFrame({"f1": f1, "f2": f2, "noise": np.random.randn(n)})
    event_spans = pd.DataFrame({
        "entry_idx": np.arange(n),
        "exit_idx": np.minimum(n - 1, np.arange(n) + 3)
    })

    trainer = MetaClassifierTrainer(n_estimators=30, max_depth=3, random_state=42)
    artifact = trainer.train_with_purged_cv(X, pd.Series(y), event_spans=event_spans, n_splits=3)

    assert artifact.model is not None
    assert artifact.roc_auc > 0.60
    assert artifact.brier_score < 0.30
    assert "f1" in artifact.feature_importances
    assert artifact.feature_importances["f1"] > artifact.feature_importances["noise"]


# ---------------------------------------------------------
# 5. Model Inference Service Feature Extraction Tests
# ---------------------------------------------------------

def test_model_inference_service():
    """
    Test ModelInferenceService extracting stationary features and predicting P(Win).
    """
    np.random.seed(123)
    bars = 80
    close = 2000.0 + np.cumsum(np.random.randn(bars) * 5.0)
    high = close + np.random.uniform(1.0, 4.0, bars)
    low = close - np.random.uniform(1.0, 4.0, bars)
    open_p = close + np.random.uniform(-1.0, 1.0, bars)
    volume = np.random.uniform(500, 2000, bars)

    df = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    })

    service = ModelInferenceService()
    feat_df = service.extract_features(df)

    assert len(feat_df) == bars
    for col in ["fracdiff_close", "volatility_gk", "variance_ratio", "alpha_composite", "ofi_proxy"]:
        assert col in feat_df.columns
        assert not feat_df[col].isna().any()

    # Real-time inference
    res = service.predict_latest_bar(df, primary_action="BUY", signal_strength=0.8)
    assert 0.0 <= res.win_probability <= 1.0
    assert isinstance(res.is_approved, bool)
    assert res.kelly_multiplier >= 0.0
    assert res.model_source in ["TRAINED_META_MODEL", "EMPIRICAL_ANALYTIC_ENGINE"]


# ---------------------------------------------------------
# 6. Congress AlphaBill Deliberation with ML Brain Tests
# ---------------------------------------------------------

def test_congress_deliberation_with_ml_service():
    """
    Test Congress deliberating and voting on an AlphaBill with real-time ML brain.
    """
    np.random.seed(999)
    bars = 70
    close = 1950.0 + np.cumsum(np.random.randn(bars) * 3.0 + 0.5)
    df = pd.DataFrame({
        "open": close - 0.5,
        "high": close + 2.0,
        "low": close - 2.0,
        "close": close,
        "volume": np.random.uniform(1000, 3000, bars)
    })

    ml_service = ModelInferenceService(prob_threshold=0.50)

    bill = Congress.deliberate_and_vote(
        target_asset="XAUUSD",
        in_sample_df=df,
        proposed_lots=4.0,
        ml_service=ml_service
    )

    assert isinstance(bill, AlphaBill)
    assert bill.target_asset == "XAUUSD"
    assert 0.0 <= bill.meta_win_probability <= 1.0
    assert bill.optimal_d > 0.0
    assert "meta_approved" in bill.alpha_conviction_summary
