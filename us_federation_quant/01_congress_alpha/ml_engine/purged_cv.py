"""
Purged and Embargoed K-Fold Cross-Validation for Financial Machine Learning.
Reference: Marcos López de Prado, Advances in Financial Machine Learning (2018), Chapter 7.

Eliminates lookahead leakage and auto-correlation bias inherent in standard K-Fold CV
by purging training samples whose labels overlap with the test evaluation span,
and imposing a post-test embargo period to remove serial correlation leakage.
"""

from typing import Generator, Tuple, List, Optional
import numpy as np
import pandas as pd


class PurgedKFold:
    """
    Purged and Embargoed Cross-Validation splitter.
    """

    def __init__(self, n_splits: int = 5, embargo_pct: float = 0.01):
        """
        :param n_splits: Number of cross-validation folds (K >= 2)
        :param embargo_pct: Percentage of total sample size applied as post-test embargo (default 1%)
        """
        if n_splits < 2:
            raise ValueError("n_splits must be at least 2.")
        self.n_splits = n_splits
        self.embargo_pct = max(0.0, embargo_pct)

    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        event_spans: Optional[pd.DataFrame] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generates purged and embargoed train/test indices.

        :param X: Feature DataFrame or array (length N)
        :param y: Optional target series
        :param event_spans: DataFrame with columns ['entry_idx', 'exit_idx'] indicating active label timespans.
                            If None, assumes entry_idx = index, exit_idx = index (point in time).
        :return: Generator of (train_indices, test_indices) arrays
        """
        n_samples = len(X)
        indices = np.arange(n_samples)

        if event_spans is None:
            # Point-in-time fallback
            starts = indices
            ends = indices
        else:
            starts = event_spans["entry_idx"].values
            ends = event_spans["exit_idx"].values

        embargo_size = int(np.ceil(n_samples * self.embargo_pct))

        # Determine contiguous fold chunks for test sets
        fold_bounds = np.linspace(0, n_samples, self.n_splits + 1, dtype=int)

        for fold in range(self.n_splits):
            test_start = fold_bounds[fold]
            test_end = fold_bounds[fold + 1]

            test_indices = indices[test_start:test_end]
            if len(test_indices) == 0:
                continue

            # Earliest start and latest end in the test fold
            min_test_time = np.min(starts[test_indices])
            max_test_time = np.max(ends[test_indices])

            # Apply Embargo limit
            embargo_limit = max_test_time + embargo_size

            train_mask = np.ones(n_samples, dtype=bool)

            # 1. Test samples cannot be in train
            train_mask[test_indices] = False

            # 2. Purging: Eliminate any training sample whose active span [start_i, end_i]
            # intersects with [min_test_time, max_test_time]
            # Overlap condition: start_i <= max_test_time and end_i >= min_test_time
            overlap = (starts <= max_test_time) & (ends >= min_test_time)
            train_mask[overlap] = False

            # 3. Embargoing: Eliminate samples starting within [max_test_time, embargo_limit]
            if embargo_size > 0:
                in_embargo = (starts > max_test_time) & (starts <= embargo_limit)
                train_mask[in_embargo] = False

            train_indices = indices[train_mask]

            yield train_indices, test_indices
