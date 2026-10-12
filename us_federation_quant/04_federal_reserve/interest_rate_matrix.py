"""
The Federal Reserve: Interest Rate Matrix & Ledoit-Wolf Covariance Denoising
Monitors cross-pod asset covariance and eliminates empirical estimation noise.
Based on Olivier Ledoit and Michael Wolf (A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices, 2004).
"""

import numpy as np
import pandas as pd
from typing import Tuple


def ledoit_wolf_covariance_shrinkage(X: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Computes analytical Ledoit-Wolf covariance matrix shrinkage:
    Sigma_shrunk = (1 - delta) * S + delta * F
    where F = (trace(S)/p) * Identity.
    """
    n, p = X.shape
    if n < 2:
        return np.eye(p), 1.0

    X_centered = X - np.mean(X, axis=0)
    S = (X_centered.T @ X_centered) / (n - 1)

    mu = np.trace(S) / p
    F = mu * np.eye(p)

    d2 = np.sum((S - F) ** 2)

    b2 = 0.0
    for i in range(n):
        row = X_centered[i:i+1, :]
        outer = row.T @ row
        b2 += np.sum((outer - S) ** 2)
    b2 /= (n ** 2)

    b2 = min(b2, d2)
    delta = 0.0 if d2 == 0 else max(0.0, min(1.0, b2 / d2))

    S_shrunk = (1.0 - delta) * S + delta * F
    return S_shrunk, float(round(delta, 4))
