"""
The Supreme Court: Deflated Sharpe Ratio (DSR) & P-Hacking Audit
Based on Marcos López de Prado (Bailey & López de Prado, 2014; AFML 2018).
Controls for selection bias under multiple testing, non-normality (skew/kurtosis), and track length.
"""

import math
import numpy as np
import pandas as pd
from typing import Tuple


def std_normal_cdf(z: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def compute_dsr_and_psr(
    returns: np.ndarray,
    num_trials: int = 10,
    benchmark_sr: float = 0.0
) -> Tuple[float, float, float]:
    """
    Computes (Annualized SR, Deflated Sharpe Ratio, Probabilistic Sharpe Ratio).
    
    :param returns: Sequence of strategy period returns
    :param num_trials: Number of trial models / strategies tested
    :param benchmark_sr: Benchmark SR
    :return: (annualized_sr, dsr, psr)
    """
    n_obs = len(returns)
    if n_obs < 10:
        return 0.0, 0.0, 0.0

    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1) + 1e-12

    sr_period = mean_ret / std_ret
    sr_annualized = sr_period * math.sqrt(252)

    skew = float(pd.Series(returns).skew())
    kurt = float(pd.Series(returns).kurtosis()) + 3.0

    # Multiple testing correction benchmark (Euler-Mascheroni constant approximation)
    if num_trials > 1:
        sr_star = math.sqrt(2.0 * math.log(num_trials)) * (1.0 - 0.5772156649 / (2.0 * math.log(num_trials)))
    else:
        sr_star = benchmark_sr

    sr_star_period = sr_star / math.sqrt(252)

    # Variance denominator
    denom = math.sqrt(max(1e-6, 1.0 - skew * sr_period + ((kurt - 1.0) / 4.0) * (sr_period ** 2)))
    
    z_dsr = ((sr_period - sr_star_period) * math.sqrt(n_obs - 1)) / denom
    dsr = std_normal_cdf(z_dsr)

    z_psr = (sr_period * math.sqrt(n_obs - 1)) / denom
    psr = std_normal_cdf(z_psr)

    return float(round(sr_annualized, 4)), float(round(dsr, 4)), float(round(psr, 4))
