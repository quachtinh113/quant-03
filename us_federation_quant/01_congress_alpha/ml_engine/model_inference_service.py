"""
Real-time Machine Learning Inference & Feature Engineering Service.
Transforms raw OHLCV market bars into stationary institutional features:
- Marcos López de Prado FFD (Fractionally Differentiated Close)
- Garman-Klass & Parkinson Extreme-Value Volatility
- Lo-MacKinlay Variance Ratio VR(q)
- Zura Kakushadze 101 Formulaic Alpha Composite
- Order Flow Imbalance (OFI) proxy

Predicts calibrated win probability P(Win = 1) for real-time trade authorization.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np
import pandas as pd

from ..formulaic_alpha_fleet.fracdiff_engine import FracDiffEngine
from ..formulaic_alpha_fleet.formulaic_alphas_101 import FormulaicAlphas101
from ..formulaic_alpha_fleet.meta_labeling_filter import MetaLabelingFilter
from ..mit_dalio_foundation.mit_matrix_compensator import MITMatrixCompensator
from .meta_classifier_trainer import MetaClassifierArtifact



@dataclass
class MLInferenceResult:
    """Real-time ML Prediction & Feature Attribution."""
    win_probability: float
    is_approved: bool
    kelly_multiplier: float
    prob_threshold: float
    features: Dict[str, float]
    model_source: str  # "TRAINED_META_MODEL" or "EMPIRICAL_ANALYTIC_ENGINE"


class ModelInferenceService:
    """
    Real-time Feature Extractor and Inference Engine.
    """

    def __init__(
        self,
        artifact: Optional[MetaClassifierArtifact] = None,
        prob_threshold: float = 0.52,
        default_d: float = 0.40
    ):
        self.artifact = artifact
        self.prob_threshold = prob_threshold
        self.default_d = default_d
        self.feature_names = [
            "fracdiff_close",
            "volatility_gk",
            "variance_ratio",
            "alpha_composite",
            "ofi_proxy",
            "momentum_5",
            "momentum_20"
        ]

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extracts stationary feature matrix from OHLCV market bars.
        """
        close = df["close"]
        high = df["high"] if "high" in df.columns else close
        low = df["low"] if "low" in df.columns else close
        volume = df["volume"] if "volume" in df.columns else pd.Series(1000.0, index=df.index)

        # 1. FracDiff Stationary Price
        frac_close = FracDiffEngine.frac_diff_ffd(close, d=self.default_d)


        # 2. Garman-Klass Extreme-Value Volatility
        log_hl = np.log(np.maximum(1e-4, high / low))
        log_co = np.log(np.maximum(1e-4, close / df.get("open", close)))
        gk_var = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
        vol_gk = pd.Series(np.sqrt(np.maximum(1e-6, gk_var)), index=df.index).rolling(10).mean().fillna(0.01)

        # 3. Lo-MacKinlay Variance Ratio (q=5)
        vr_vals = []
        for i in range(len(close)):
            if i < 25:
                vr_vals.append(1.0)
            else:
                sub_close = close.iloc[i - 25:i + 1]
                audit = MITMatrixCompensator.lo_mackinlay_variance_ratio(sub_close.values, q=5)
                vr_vals.append(audit.variance_ratio)

        vr_series = pd.Series(vr_vals, index=df.index)

        # 4. Kakushadze Alphas Composite (Alpha 001 + 006 + 012 + 054 + 101)
        a1 = FormulaicAlphas101.alpha_001(df)
        a6 = FormulaicAlphas101.alpha_006(df)
        a12 = FormulaicAlphas101.alpha_012(df)
        a54 = FormulaicAlphas101.alpha_054(df)
        a101 = FormulaicAlphas101.alpha_101(df)
        alpha_composite = pd.Series(
            0.25 * np.tanh(a1 * 2.0) + 0.20 * np.tanh(a6) + 0.15 * np.tanh(a12 * 0.5) +
            0.15 * np.tanh(a54 * 0.5) + 0.25 * np.tanh(a101 * 2.0),
            index=df.index
        ).fillna(0.0)


        # 5. Order Flow Imbalance proxy (Close position within bar * Volume)
        spread = np.maximum(1e-4, high - low)
        bar_pos = ((close - low) - (high - close)) / spread
        ofi_proxy = (bar_pos * np.log1p(volume)).rolling(10).mean().fillna(0.0)

        # 6. Returns Momentum
        mom5 = close.pct_change(5).fillna(0.0)
        mom20 = close.pct_change(20).fillna(0.0)

        feature_df = pd.DataFrame({
            "fracdiff_close": frac_close,
            "volatility_gk": vol_gk,
            "variance_ratio": vr_series,
            "alpha_composite": alpha_composite,
            "ofi_proxy": ofi_proxy,
            "momentum_5": mom5,
            "momentum_20": mom20
        }, index=df.index).fillna(0.0)

        return feature_df

    def predict_latest_bar(
        self,
        df: pd.DataFrame,
        primary_action: str = "BUY",
        signal_strength: float = 0.5
    ) -> MLInferenceResult:
        """
        Extracts features at the latest bar and computes calibrated P(Win) and Kelly multiplier.
        """
        features_df = self.extract_features(df)
        latest_row = features_df.iloc[-1]
        feature_dict = {col: round(float(latest_row[col]), 5) for col in features_df.columns}

        if self.artifact is not None and self.artifact.model is not None:
            # Align features with training artifact
            feature_vector = np.array([[latest_row.get(f, 0.0) for f in self.artifact.feature_names]])
            raw_prob = float(self.artifact.model.predict_proba(feature_vector)[0, 1])
            model_source = "TRAINED_META_MODEL"
        else:
            # Analytic empirical Bayesian prior
            # Combine signal strength + variance ratio trend boost + alpha composite
            base_prob = 0.50
            alpha_boost = np.clip(latest_row["alpha_composite"], -0.15, 0.15)
            vr_boost = 0.05 if latest_row["variance_ratio"] > 1.20 else (-0.05 if latest_row["variance_ratio"] < 0.80 else 0.0)
            mom_sign = 1.0 if primary_action.upper() == "BUY" else -1.0
            mom_boost = float(np.clip(latest_row["momentum_5"] * mom_sign * 5.0, -0.10, 0.10))

            raw_prob = float(np.clip(base_prob + alpha_boost + vr_boost + mom_boost + 0.05 * signal_strength, 0.05, 0.95))
            model_source = "EMPIRICAL_ANALYTIC_ENGINE"

        win_prob = round(raw_prob, 4)
        is_approved = win_prob >= self.prob_threshold

        # Compute Fractional Kelly multiplier
        _, kelly_mult = MetaLabelingFilter.compute_fractional_kelly(
            win_prob=win_prob,
            payout_ratio_b=1.5,
            kelly_fraction_lambda=0.50
        )

        return MLInferenceResult(
            win_probability=win_prob,
            is_approved=is_approved,
            kelly_multiplier=kelly_mult if is_approved else 0.0,
            prob_threshold=self.prob_threshold,
            features=feature_dict,
            model_source=model_source
        )
