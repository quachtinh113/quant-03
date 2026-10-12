"""
The Fourth Estate / Central Risk Desk: VaR & CVaR (Expected Shortfall) Engine.
Calculates Value at Risk (VaR) and Expected Shortfall (CVaR) across 3 distinct methodologies:
1. Parametric (Variance-Covariance)
2. Historical Simulation
3. Monte Carlo Simulation (10,000 correlated multivariate paths)
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import scipy.stats as stats


@dataclass
class VaRMetricResult:
    """Quantitative risk metrics at a specific confidence level."""
    confidence_level: float
    parametric_var_pct: float
    parametric_var_dollar: float
    historical_var_pct: float
    historical_var_dollar: float
    historical_cvar_pct: float
    historical_cvar_dollar: float
    monte_carlo_var_pct: float
    monte_carlo_var_dollar: float
    monte_carlo_cvar_pct: float
    monte_carlo_cvar_dollar: float
    portfolio_equity: float


class CentralVaREngine:
    """
    Central Risk Desk VaR & CVaR Calculation Engine.
    Enforces Basel III / Institutional Hedge Fund risk quantification.
    """

    def __init__(self, default_confidence: float = 0.99):
        self.default_confidence = default_confidence

    def calculate_parametric_var(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        portfolio_equity: float,
        confidence_level: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculates parametric VaR using analytical Variance-Covariance method.
        VaR = z_alpha * sigma_port * Portfolio_Equity
        """
        alpha = confidence_level if confidence_level is not None else self.default_confidence
        weights = np.asarray(weights, dtype=float)
        cov_matrix = np.asarray(cov_matrix, dtype=float)

        port_variance = float(weights.T @ cov_matrix @ weights)
        port_sigma = float(np.sqrt(max(port_variance, 1e-12)))

        z_score = float(stats.norm.ppf(alpha))
        var_pct = float(z_score * port_sigma)
        var_dollar = float(var_pct * portfolio_equity)

        return {
            "var_pct": round(var_pct, 6),
            "var_dollar": round(var_dollar, 2),
            "port_sigma": round(port_sigma, 6),
            "z_score": round(z_score, 4)
        }

    def calculate_historical_var_cvar(
        self,
        historical_returns: np.ndarray,
        weights: np.ndarray,
        portfolio_equity: float,
        confidence_level: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculates Historical Simulation VaR and CVaR (Expected Shortfall).
        CVaR = Mean of losses strictly worse than the VaR threshold.
        """
        alpha = confidence_level if confidence_level is not None else self.default_confidence
        historical_returns = np.asarray(historical_returns, dtype=float)
        weights = np.asarray(weights, dtype=float)

        # Compute portfolio historical return series: shape (N_obs,)
        if historical_returns.ndim == 1:
            port_returns = historical_returns
        else:
            port_returns = historical_returns @ weights

        # Losses are negative returns: L = -R
        losses = -port_returns
        percentile_level = alpha * 100.0
        var_pct = float(np.percentile(losses, percentile_level))
        var_dollar = float(var_pct * portfolio_equity)

        # CVaR is the average loss beyond VaR
        tail_losses = losses[losses >= var_pct]
        if len(tail_losses) > 0:
            cvar_pct = float(np.mean(tail_losses))
        else:
            cvar_pct = var_pct

        cvar_dollar = float(cvar_pct * portfolio_equity)

        return {
            "var_pct": round(var_pct, 6),
            "var_dollar": round(var_dollar, 2),
            "cvar_pct": round(cvar_pct, 6),
            "cvar_dollar": round(cvar_dollar, 2)
        }

    def calculate_monte_carlo_var_cvar(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        mean_returns: Optional[np.ndarray],
        portfolio_equity: float,
        num_simulations: int = 10_000,
        confidence_level: Optional[float] = None,
        random_seed: int = 42
    ) -> Dict[str, float]:
        """
        Calculates Monte Carlo VaR and CVaR using correlated multivariate normal draws.
        """
        alpha = confidence_level if confidence_level is not None else self.default_confidence
        weights = np.asarray(weights, dtype=float)
        cov_matrix = np.asarray(cov_matrix, dtype=float)
        n_assets = len(weights)

        if mean_returns is None:
            mean_returns = np.zeros(n_assets)
        else:
            mean_returns = np.asarray(mean_returns, dtype=float)

        np.random.seed(random_seed)
        # SVD or Cholesky for positive semi-definite covariance
        try:
            L = np.linalg.cholesky(cov_matrix)
            standard_draws = np.random.randn(num_simulations, n_assets)
            simulated_asset_returns = mean_returns + (standard_draws @ L.T)
        except np.linalg.LinAlgError:
            # Fallback to eigen decomposition if not strictly positive definite
            vals, vecs = np.linalg.eigh(cov_matrix)
            vals = np.maximum(vals, 1e-12)
            sqrt_cov = vecs @ np.diag(np.sqrt(vals))
            standard_draws = np.random.randn(num_simulations, n_assets)
            simulated_asset_returns = mean_returns + (standard_draws @ sqrt_cov.T)

        simulated_port_returns = simulated_asset_returns @ weights
        losses = -simulated_port_returns

        var_pct = float(np.percentile(losses, alpha * 100.0))
        var_dollar = float(var_pct * portfolio_equity)

        tail_losses = losses[losses >= var_pct]
        cvar_pct = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_pct
        cvar_dollar = float(cvar_pct * portfolio_equity)

        return {
            "var_pct": round(var_pct, 6),
            "var_dollar": round(var_dollar, 2),
            "cvar_pct": round(cvar_pct, 6),
            "cvar_dollar": round(cvar_dollar, 2),
            "num_simulations": num_simulations
        }

    def compute_comprehensive_risk_report(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        historical_returns: np.ndarray,
        portfolio_equity: float,
        confidence_level: float = 0.99
    ) -> VaRMetricResult:
        """
        Synthesizes parametric, historical, and Monte Carlo risk metrics into a single unified verdict.
        """
        param_res = self.calculate_parametric_var(weights, cov_matrix, portfolio_equity, confidence_level)
        hist_res = self.calculate_historical_var_cvar(historical_returns, weights, portfolio_equity, confidence_level)
        mc_res = self.calculate_monte_carlo_var_cvar(
            weights, cov_matrix, None, portfolio_equity,
            num_simulations=10_000, confidence_level=confidence_level
        )

        return VaRMetricResult(
            confidence_level=confidence_level,
            parametric_var_pct=param_res["var_pct"],
            parametric_var_dollar=param_res["var_dollar"],
            historical_var_pct=hist_res["var_pct"],
            historical_var_dollar=hist_res["var_dollar"],
            historical_cvar_pct=hist_res["cvar_pct"],
            historical_cvar_dollar=hist_res["cvar_dollar"],
            monte_carlo_var_pct=mc_res["var_pct"],
            monte_carlo_var_dollar=mc_res["var_dollar"],
            monte_carlo_cvar_pct=mc_res["cvar_pct"],
            monte_carlo_cvar_dollar=mc_res["cvar_dollar"],
            portfolio_equity=portfolio_equity
        )
