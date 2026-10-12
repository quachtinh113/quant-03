"""
The Fourth Estate Telemetry & Independent Watchdog.
Monitors live execution quality, detects broker slippage anomalies,
audits execution latency, and issues investigative risk bulletins.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time


class SlippageAnomalyAlert(Exception):
    """Raised when broker execution slippage exceeds constitutional threshold."""
    pass


class ExecutionLatencyAlert(Exception):
    """Raised when execution latency exceeds acceptable real-time threshold."""
    pass


@dataclass
class TelemetryAuditRecord:
    """Audit log entry for a single trade execution."""
    timestamp: float
    asset: str
    action: str
    theoretical_price: float
    fill_price: float
    slippage_bps: float
    latency_ms: float
    is_anomaly: bool
    details: str = ""


@dataclass
class RiskIntelligenceDispatch:
    """Published investigative risk intelligence bulletin."""
    total_fills_audited: int
    anomalies_detected: int
    mean_slippage_bps: float
    max_slippage_bps: float
    mean_latency_ms: float
    integrity_score: float  # 0.0 to 100.0
    status: str             # "CLEAN", "WARNING", "COMPROMISED"
    findings: List[str] = field(default_factory=list)


class FourthEstateWatchdog:
    """
    Independent Press & Telemetry Watchdog.
    Audits live execution vs theoretical backtest prices with zero compromise.
    """

    def __init__(
        self,
        max_allowed_slippage_bps: float = 12.0,
        max_allowed_latency_ms: float = 250.0
    ):
        self.max_allowed_slippage_bps = max_allowed_slippage_bps
        self.max_allowed_latency_ms = max_allowed_latency_ms
        self.audit_log: List[TelemetryAuditRecord] = []
        self.anomalies_count: int = 0

    def audit_fill(
        self,
        theoretical_price: float,
        fill_price: float,
        action: str,
        asset: str = "XAUUSD",
        latency_ms: float = 25.0
    ) -> TelemetryAuditRecord:
        """
        Audits a live execution fill against its theoretical benchmark price.
        Slippage bps = (Diff / Theoretical) * 10000.
        """
        if theoretical_price <= 0:
            raise ValueError(f"Theoretical price must be positive: {theoretical_price}")

        if action.upper() == "BUY":
            slippage_diff = fill_price - theoretical_price
        else:
            slippage_diff = theoretical_price - fill_price

        slippage_bps = (slippage_diff / theoretical_price) * 10000.0
        is_anomaly = bool(slippage_bps > self.max_allowed_slippage_bps)

        if is_anomaly:
            self.anomalies_count += 1

        record = TelemetryAuditRecord(
            timestamp=time.time(),
            asset=asset,
            action=action.upper(),
            theoretical_price=round(theoretical_price, 5),
            fill_price=round(fill_price, 5),
            slippage_bps=round(slippage_bps, 2),
            latency_ms=round(latency_ms, 2),
            is_anomaly=is_anomaly,
            details="Adverse slippage detected" if is_anomaly else "Normal execution"
        )
        self.audit_log.append(record)

        if is_anomaly:
            raise SlippageAnomalyAlert(
                f"Fourth Estate Alert: Execution slippage {record.slippage_bps} bps "
                f"exceeds limit {self.max_allowed_slippage_bps} bps for {asset} {action}."
            )

        return record

    def publish_risk_dispatch(self) -> RiskIntelligenceDispatch:
        """
        Compiles all audit records into an official investigative dispatch.
        """
        if not self.audit_log:
            return RiskIntelligenceDispatch(
                total_fills_audited=0,
                anomalies_detected=0,
                mean_slippage_bps=0.0,
                max_slippage_bps=0.0,
                mean_latency_ms=0.0,
                integrity_score=100.0,
                status="CLEAN",
                findings=["No execution fills recorded yet."]
            )

        slippages = [r.slippage_bps for r in self.audit_log]
        latencies = [r.latency_ms for r in self.audit_log]

        mean_slip = float(sum(slippages) / len(slippages))
        max_slip = float(max(slippages))
        mean_lat = float(sum(latencies) / len(latencies))

        # Integrity score degradation
        penalty = (self.anomalies_count * 15.0) + max(0.0, (mean_slip - 5.0) * 2.0)
        score = max(0.0, min(100.0, 100.0 - penalty))

        findings = []
        if self.anomalies_count > 0:
            findings.append(f"Detected {self.anomalies_count} critical slippage anomalies.")
        if mean_lat > self.max_allowed_latency_ms:
            findings.append(f"Mean latency {round(mean_lat, 1)}ms exceeds {self.max_allowed_latency_ms}ms.")

        if score >= 85.0:
            status = "CLEAN"
        elif score >= 60.0:
            status = "WARNING"
        else:
            status = "COMPROMISED"

        if not findings:
            findings.append("Broker execution quality satisfies all institutional standards.")

        return RiskIntelligenceDispatch(
            total_fills_audited=len(self.audit_log),
            anomalies_detected=self.anomalies_count,
            mean_slippage_bps=round(mean_slip, 2),
            max_slippage_bps=round(max_slip, 2),
            mean_latency_ms=round(mean_lat, 2),
            integrity_score=round(score, 1),
            status=status,
            findings=findings
        )
