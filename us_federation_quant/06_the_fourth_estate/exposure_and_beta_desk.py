"""
The Fourth Estate / Central Risk Desk: Gross/Net Exposure & Dollar Beta Desk.
Enforces institutional Market Neutrality (|Beta_port| <= 0.05), Gross Leverage Limits,
and Herfindahl-Hirschman Index (HHI) concentration limits.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import numpy as np


@dataclass
class PositionSnapshot:
    """Individual position snapshot for exposure auditing."""
    asset: str
    notional_value: float  # Positive for Long, Negative for Short
    asset_beta: float      # Beta against SPY / Global benchmark
    adv_pct: float = 0.01  # Fraction of 30-day Average Daily Volume (ADV)


@dataclass
class ExposureAndBetaReport:
    """Full Exposure and Beta Audit Report."""
    portfolio_equity: float
    gross_exposure_dollar: float
    gross_leverage: float
    net_exposure_dollar: float
    net_leverage: float
    portfolio_market_beta: float
    is_market_neutral: bool
    hhi_concentration: float
    max_single_asset_exposure_pct: float
    is_compliant: bool
    violations: List[str] = field(default_factory=list)


class ExposureAndBetaDesk:
    """
    Independent Risk Desk enforcing Leverage, Market Neutrality, and Concentration Limits.
    Based on Millennium / Citadel multi-manager mandate.
    """

    def __init__(
        self,
        max_gross_leverage: float = 4.0,
        max_net_leverage: float = 0.20,
        max_market_beta: float = 0.05,
        max_hhi_concentration: float = 0.35,
        max_single_asset_pct: float = 0.40
    ):
        self.max_gross_leverage = max_gross_leverage
        self.max_net_leverage = max_net_leverage
        self.max_market_beta = max_market_beta
        self.max_hhi_concentration = max_hhi_concentration
        self.max_single_asset_pct = max_single_asset_pct

    def audit_positions(
        self,
        positions: List[PositionSnapshot],
        portfolio_equity: float
    ) -> ExposureAndBetaReport:
        """
        Audits current book positions against constitutional risk constraints.
        """
        if portfolio_equity <= 0:
            raise ValueError(f"Portfolio equity must be strictly positive: {portfolio_equity}")

        if not positions:
            return ExposureAndBetaReport(
                portfolio_equity=portfolio_equity,
                gross_exposure_dollar=0.0,
                gross_leverage=0.0,
                net_exposure_dollar=0.0,
                net_leverage=0.0,
                portfolio_market_beta=0.0,
                is_market_neutral=True,
                hhi_concentration=0.0,
                max_single_asset_exposure_pct=0.0,
                is_compliant=True,
                violations=[]
            )

        notionals = np.array([p.notional_value for p in positions], dtype=float)
        betas = np.array([p.asset_beta for p in positions], dtype=float)

        gross_exposure = float(np.sum(np.abs(notionals)))
        net_exposure = float(np.sum(notionals))

        gross_leverage = float(gross_exposure / portfolio_equity)
        net_leverage = float(abs(net_exposure) / portfolio_equity)

        # Portfolio beta weighted by equity allocation: beta_port = sum( (V_i / Equity) * beta_i )
        portfolio_beta = float(np.sum((notionals / portfolio_equity) * betas))

        # HHI Concentration: sum( ( |V_i| / Gross )^2 )
        if gross_exposure > 1e-6:
            weights = np.abs(notionals) / gross_exposure
            hhi = float(np.sum(weights ** 2))
            max_single_pct = float(np.max(weights))
        else:
            hhi = 0.0
            max_single_pct = 0.0

        violations = []

        # 1. Gross leverage check
        if gross_leverage > self.max_gross_leverage:
            violations.append(
                f"Gross leverage {round(gross_leverage, 2)}x exceeds limit {self.max_gross_leverage}x"
            )

        # 2. Net leverage check
        if net_leverage > self.max_net_leverage:
            violations.append(
                f"Net leverage {round(net_leverage, 2)}x exceeds limit {self.max_net_leverage}x"
            )

        # 3. Market Beta neutrality check (|beta| <= 0.05)
        is_neutral = bool(abs(portfolio_beta) <= self.max_market_beta)
        if not is_neutral:
            violations.append(
                f"Portfolio Market Beta {round(portfolio_beta, 4)} violates neutrality limit |beta| <= {self.max_market_beta}"
            )

        # 4. HHI concentration check
        if hhi > self.max_hhi_concentration:
            violations.append(
                f"HHI Concentration {round(hhi, 4)} exceeds limit {self.max_hhi_concentration}"
            )

        # 5. Single asset cap
        if max_single_pct > self.max_single_asset_pct:
            violations.append(
                f"Single asset concentration {round(max_single_pct * 100, 1)}% exceeds limit {self.max_single_asset_pct * 100}%"
            )

        is_compliant = (len(violations) == 0)

        return ExposureAndBetaReport(
            portfolio_equity=portfolio_equity,
            gross_exposure_dollar=round(gross_exposure, 2),
            gross_leverage=round(gross_leverage, 4),
            net_exposure_dollar=round(net_exposure, 2),
            net_leverage=round(net_leverage, 4),
            portfolio_market_beta=round(portfolio_beta, 4),
            is_market_neutral=is_neutral,
            hhi_concentration=round(hhi, 4),
            max_single_asset_exposure_pct=round(max_single_pct, 4),
            is_compliant=is_compliant,
            violations=violations
        )
