"""
Central Risk Desk (The Chief Risk Officer & Fourth Estate Facade).
Integrates all 4 risk pillars:
1. VaR & CVaR Engine (Parametric, Historical, Monte Carlo)
2. Exposure & Market Beta Neutrality Desk (|beta| <= 0.05, Leverage <= 4.0x)
3. Fourth Estate Watchdog (Slippage & Broker Telemetry)
4. Federal Master Kill-Switch (Totalitarian Drawdown Circuit Breaker)
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np

from .var_cvar_engine import CentralVaREngine, VaRMetricResult
from .exposure_and_beta_desk import ExposureAndBetaDesk, ExposureAndBetaReport, PositionSnapshot
from .fourth_estate_watchdog import FourthEstateWatchdog, RiskIntelligenceDispatch, TelemetryAuditRecord
from .federal_master_kill_switch import FederalMasterKillSwitch, KillSwitchDirective, FederalCircuitBreakerActive


@dataclass
class CentralRiskAuditReport:
    """Master Comprehensive Risk Audit Report."""
    portfolio_equity: float
    overall_status: str              # "APPROVED", "CAUTION_WARNING", "CRITICAL_VETO"
    is_approved_for_trading: bool
    var_metrics: Optional[VaRMetricResult]
    exposure_report: ExposureAndBetaReport
    kill_switch_directive: KillSwitchDirective
    telemetry_dispatch: RiskIntelligenceDispatch
    action_recommendations: List[str]


class CentralRiskDesk:
    """
    The Supreme Central Risk Authority (Chief Risk Officer Desk).
    Guarantees that the US Federation Quant portfolio strictly preserves capital,
    maintains market neutrality, and enforces institutional discipline.
    """

    def __init__(
        self,
        var_confidence: float = 0.99,
        max_gross_leverage: float = 4.0,
        max_net_leverage: float = 0.20,
        max_market_beta: float = 0.05,
        max_allowed_slippage_bps: float = 15.0,
        kill_switch_red_threshold: float = -0.12
    ):
        self.var_engine = CentralVaREngine(default_confidence=var_confidence)
        self.exposure_desk = ExposureAndBetaDesk(
            max_gross_leverage=max_gross_leverage,
            max_net_leverage=max_net_leverage,
            max_market_beta=max_market_beta
        )
        self.watchdog = FourthEstateWatchdog(max_allowed_slippage_bps=max_allowed_slippage_bps)
        self.kill_switch = FederalMasterKillSwitch(red_threshold=kill_switch_red_threshold)

    def audit_entire_federation(
        self,
        portfolio_equity: float,
        positions: List[PositionSnapshot],
        historical_returns: Optional[np.ndarray] = None,
        asset_weights: Optional[np.ndarray] = None,
        cov_matrix: Optional[np.ndarray] = None,
        broker_connector: Optional[Any] = None
    ) -> CentralRiskAuditReport:
        """
        Executes an exhaustive 360-degree risk examination across the entire federation.
        """
        # 1. Update equity and check master kill switch
        ks_directive = self.kill_switch.update_equity(portfolio_equity, broker_connector=broker_connector)

        # 2. Audit book exposure and market beta
        exposure_rep = self.exposure_desk.audit_positions(positions, portfolio_equity)

        # 3. Audit VaR and Expected Shortfall if covariance/returns supplied
        var_metrics = None
        if historical_returns is not None and asset_weights is not None and cov_matrix is not None:
            var_metrics = self.var_engine.compute_comprehensive_risk_report(
                weights=asset_weights,
                cov_matrix=cov_matrix,
                historical_returns=historical_returns,
                portfolio_equity=portfolio_equity
            )

        # 4. Watchdog telemetry dispatch
        dispatch = self.watchdog.publish_risk_dispatch()

        # 5. Synthesize master risk status
        actions = []
        if ks_directive.is_trading_locked:
            overall_status = "CRITICAL_VETO"
            is_approved = False
            actions.append(f"KILL-SWITCH ENGAGED: {ks_directive.reason}")
        elif not exposure_rep.is_compliant:
            overall_status = "CAUTION_WARNING" if ks_directive.status_level == "NORMAL" else "CRITICAL_VETO"
            is_approved = (overall_status != "CRITICAL_VETO")
            actions.extend([f"Exposure Breach: {v}" for v in exposure_rep.violations])
        elif ks_directive.status_level in ["YELLOW_ALERT", "ORANGE_ALERT"]:
            overall_status = "CAUTION_WARNING"
            is_approved = True
            actions.append(f"Drawdown Alert ({ks_directive.status_level}): Scale positions by {ks_directive.position_scale_factor}x")
        else:
            overall_status = "APPROVED"
            is_approved = True
            actions.append("All risk parameters within institutional tolerances.")

        return CentralRiskAuditReport(
            portfolio_equity=portfolio_equity,
            overall_status=overall_status,
            is_approved_for_trading=is_approved,
            var_metrics=var_metrics,
            exposure_report=exposure_rep,
            kill_switch_directive=ks_directive,
            telemetry_dispatch=dispatch,
            action_recommendations=actions
        )

    def verify_order_clearance(self, order_lots: float, asset_notional: float) -> float:
        """
        Pre-trade risk clearance gate.
        Returns scaled allowed lots (scaled down during Yellow/Orange alerts),
        or raises FederalCircuitBreakerActive if locked.
        """
        self.kill_switch.verify_order_permission()
        scale = 1.0
        if len(self.kill_switch.incident_history) > 0:
            scale = self.kill_switch.incident_history[-1].position_scale_factor

        return round(order_lots * scale, 2)

    def audit_trade_fill(
        self,
        theoretical_price: float,
        fill_price: float,
        action: str,
        asset: str = "XAUUSD",
        latency_ms: float = 25.0
    ) -> TelemetryAuditRecord:
        """Audits live execution fill against theoretical signal."""
        return self.watchdog.audit_fill(
            theoretical_price=theoretical_price,
            fill_price=fill_price,
            action=action,
            asset=asset,
            latency_ms=latency_ms
        )
