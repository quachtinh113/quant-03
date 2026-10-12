"""
Meta-Classifier Model Training Pipeline for Financial Machine Learning.
Reference: Marcos López de Prado, Advances in Financial Machine Learning (2018), Chapter 3 & 10.

Trains a secondary classification model to predict whether a primary trading signal
will achieve its profit target before stopping out: y in {0, 1}.
Incorporates Purged & Embargoed Cross-Validation, Probability Calibration,
and Brier Score / ROC-AUC diagnostics.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score, precision_score

from .purged_cv import PurgedKFold


@dataclass
class MetaClassifierArtifact:
    """Trained Meta-Classifier model and validation diagnostics."""
    model: Any
    feature_names: List[str]
    roc_auc: float
    brier_score: float
    accuracy: float
    precision_at_threshold: float
    oof_predictions: np.ndarray
    feature_importances: Dict[str, float]
    n_samples: int
    n_features: int


class MetaClassifierTrainer:
    """
    Automated Trainer for Meta-Labeling Probability Models.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        min_samples_leaf: int = 10,
        random_state: int = 42,
        prob_threshold: float = 0.52
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state
        self.prob_threshold = prob_threshold

    def train_with_purged_cv(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        event_spans: Optional[pd.DataFrame] = None,
        n_splits: int = 4,
        embargo_pct: float = 0.01
    ) -> MetaClassifierArtifact:
        """
        Trains and validates the Meta-Classifier using Purged & Embargoed Cross-Validation.

        :param X: Feature matrix DataFrame
        :param y: Target binary labels (0 or 1)
        :param event_spans: DataFrame with ['entry_idx', 'exit_idx'] for overlap purging
        :param n_splits: Number of CV folds
        :param embargo_pct: Embargo percentage
        :return: MetaClassifierArtifact containing calibrated model and diagnostics
        """
        feature_names = list(X.columns)
        n_samples = len(X)
        X_mat = X.values
        y_vec = y.values.astype(int)

        oof_probs = np.zeros(n_samples)
        cv = PurgedKFold(n_splits=n_splits, embargo_pct=embargo_pct)

        # Out-of-fold evaluation loop
        for train_idx, test_idx in cv.split(X, y, event_spans=event_spans):
            if len(train_idx) == 0 or len(test_idx) == 0:
                continue

            # Base tree estimator
            base_rf = RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                random_state=self.random_state,
                n_jobs=-1
            )

            # Fit fold model
            base_rf.fit(X_mat[train_idx], y_vec[train_idx])

            # Predict probabilities on test fold
            if len(np.unique(y_vec[train_idx])) > 1:
                test_probs = base_rf.predict_proba(X_mat[test_idx])[:, 1]
            else:
                test_probs = np.full(len(test_idx), float(y_vec[train_idx][0]))

            oof_probs[test_idx] = test_probs

        # Calculate Out-of-Fold Diagnostics
        valid_mask = oof_probs > 0  # Evaluate where OOF predictions were populated
        if np.sum(valid_mask) > 10 and len(np.unique(y_vec[valid_mask])) > 1:
            auc = float(roc_auc_score(y_vec[valid_mask], oof_probs[valid_mask]))
            brier = float(brier_score_loss(y_vec[valid_mask], oof_probs[valid_mask]))
            binary_preds = (oof_probs[valid_mask] >= self.prob_threshold).astype(int)
            acc = float(accuracy_score(y_vec[valid_mask], binary_preds))
            prec = float(precision_score(y_vec[valid_mask], binary_preds, zero_division=0))
        else:
            auc = 0.50
            brier = 0.25
            acc = float(np.mean(y_vec == 1))
            prec = 0.50

        # Fit final full model
        full_rf = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            random_state=self.random_state,
            n_jobs=-1
        )
        full_rf.fit(X_mat, y_vec)

        # Calibrate probabilities using sigmoid scaling if multi-class
        if len(np.unique(y_vec)) > 1:
            try:
                calibrated_model = CalibratedClassifierCV(estimator=full_rf, method="sigmoid", cv=2)
                calibrated_model.fit(X_mat, y_vec)
            except Exception:
                calibrated_model = full_rf
        else:
            calibrated_model = full_rf


        # Feature importances
        raw_importances = full_rf.feature_importances_
        feature_importances = {
            feature_names[i]: round(float(raw_importances[i]), 4)
            for i in range(len(feature_names))
        }

        return MetaClassifierArtifact(
            model=calibrated_model,
            feature_names=feature_names,
            roc_auc=round(auc, 4),
            brier_score=round(brier, 4),
            accuracy=round(acc, 4),
            precision_at_threshold=round(prec, 4),
            oof_predictions=oof_probs,
            feature_importances=feature_importances,
            n_samples=n_samples,
            n_features=len(feature_names)
        )
