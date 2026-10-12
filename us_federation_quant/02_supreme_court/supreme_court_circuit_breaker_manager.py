"""
========================================================================================
US FEDERATION QUANT — SUPREME COURT AUTO-QUARANTINE & CIRCUIT BREAKER MANAGER
Module: 02_supreme_court/supreme_court_circuit_breaker_manager.py
Adversarial Constitutional Risk & Circuit Breaker Enforcement Desk.

Constitutional Mandates:
1. Pod Local Drawdown Ladder:
   - DD <= -3.0%: DELEVERAGED_50 (Scale down lot size by 50%).
   - DD <= -5.0%: QUARANTINED (Circuit Breaker: Flatten active orders, freeze state pod).
2. Portfolio Systemic Drawdown Nuclear Cap:
   - DD <= -7.5%: NUCLEAR_FLATTEN (Emergency flatten ALL positions across 50 states).
3. Pairwise Correlation Spike Circuit Breaker:
   - Pairwise correlation > 0.85 on > 10 pairs -> De-lever overall portfolio by 50%.
4. Exness Rollover Curfew & Red Macro News Embargo:
   - Auto-lock order routing during 21:45 - 22:15 UTC & NFP/CPI/FOMC blackout windows.
========================================================================================
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE = _DIR.parent
for p in [str(_DIR), str(_WORKSPACE)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from us_federation_quant.institutional_governance_rules import (
    InstitutionalStatutoryRules,
    StatutoryAuditResult,
)

LOG_DIR = _DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_QUARANTINE_REGISTRY_PATH = LOG_DIR / "supreme_court_quarantine_registry.json"

logger = logging.getLogger("SupremeCourtCircuitBreaker")


@dataclass
class PodQuarantineRecord:
    state_id: str
    state_name: str
    primary_asset: str
    allocated_capital: float
    current_equity: float
    peak_equity: float
    local_drawdown_pct: float
    quarantine_status: str  # NORMAL | DELEVERAGED_50 | QUARANTINED
    circuit_breaker_active: bool
    last_audit_timestamp: str
    quarantine_reason: str


@dataclass
class SystemCircuitBreakerSnapshot:
    timestamp_utc: str
    total_portfolio_equity: float
    peak_portfolio_equity: float
    portfolio_drawdown_pct: float
    nuclear_football_triggered: bool
    correlation_spike_triggered: bool
    active_quarantined_states_count: int
    active_deleveraged_states_count: int
    active_normal_states_count: int
    quarantine_registry: Dict[str, PodQuarantineRecord]


class SupremeCourtCircuitBreakerManager:
    """
    Tòa án Tối cao: Bộ Quản trị Rủi ro Ngắt mạch Tự động (Auto-Quarantine & Circuit Breaker Manager).
    """

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or _QUARANTINE_REGISTRY_PATH
        self.quarantine_registry: Dict[str, PodQuarantineRecord] = {}
        self.portfolio_peak_equity: float = 10_000.0
        self.nuclear_football_triggered: bool = False
        self._load_registry()

    def _load_registry(self):
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.portfolio_peak_equity = float(data.get("portfolio_peak_equity", 10_000.0))
                    self.nuclear_football_triggered = bool(data.get("nuclear_football_triggered", False))
                    raw_pods = data.get("quarantine_registry", {})
                    for sid, record in raw_pods.items():
                        self.quarantine_registry[sid] = PodQuarantineRecord(**record)
            except Exception as e:
                logger.warning(f"Could not load Supreme Court quarantine registry: {e}")

    def _save_registry(self, snapshot: SystemCircuitBreakerSnapshot):
        try:
            dict_registry = {sid: asdict(rec) for sid, rec in snapshot.quarantine_registry.items()}
            data = {
                "timestamp_utc": snapshot.timestamp_utc,
                "portfolio_peak_equity": snapshot.peak_portfolio_equity,
                "portfolio_drawdown_pct": snapshot.portfolio_drawdown_pct,
                "nuclear_football_triggered": snapshot.nuclear_football_triggered,
                "correlation_spike_triggered": snapshot.correlation_spike_triggered,
                "active_quarantined_states_count": snapshot.active_quarantined_states_count,
                "active_deleveraged_states_count": snapshot.active_deleveraged_states_count,
                "active_normal_states_count": snapshot.active_normal_states_count,
                "quarantine_registry": dict_registry,
            }
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error persisting Supreme Court quarantine registry: {e}")

    def audit_and_enforce_state_pod(
        self,
        state_id: str,
        state_name: str,
        primary_asset: str,
        allocated_capital: float,
        current_equity: float,
        peak_equity: float,
    ) -> PodQuarantineRecord:
        """
        Audit 1 State Pod against the Statutory Drawdown Ladder (-3%, -5%).
        """
        peak = max(allocated_capital, peak_equity)
        dd = (peak - current_equity) / peak if peak > 0 else 0.0
        dd_pct = round(dd * 100.0, 2)
        now_str = datetime.now(timezone.utc).isoformat()

        status = "NORMAL"
        cb_active = False
        reason = "Hoạt động bình thường dưới hạn mức an toàn."

        if dd >= 0.05:  # Local DD >= 5.0%
            status = "QUARANTINED"
            cb_active = True
            reason = (
                f"[TÒA ÁN TỐI CAO - KHÓA PHONG TỎA] Local Drawdown {dd_pct}% >= 5.0%. "
                f"Tự động kích hoạt Circuit Breaker: ĐÓNG TOÀN BỘ VỊ THẾ & PHONG TỎA MỞ LỆNH MỚI!"
            )
            logger.error(f"🚨 {state_id} ({primary_asset}): {reason}")
        elif dd >= 0.03:  # Local DD >= 3.0%
            status = "DELEVERAGED_50"
            cb_active = False
            reason = (
                f"[TÒA ÁN TỐI CAO - CẢNH BÁO GIẢM ĐÒN BẨY] Local Drawdown {dd_pct}% >= 3.0%. "
                f"Tự động áp dụng hệ số cắt giảm 50% lot size!"
            )
            logger.warning(f"⚠️ {state_id} ({primary_asset}): {reason}")

        record = PodQuarantineRecord(
            state_id=state_id,
            state_name=state_name,
            primary_asset=primary_asset,
            allocated_capital=allocated_capital,
            current_equity=current_equity,
            peak_equity=peak,
            local_drawdown_pct=dd_pct,
            quarantine_status=status,
            circuit_breaker_active=cb_active,
            last_audit_timestamp=now_str,
            quarantine_reason=reason,
        )

        self.quarantine_registry[state_id] = record
        return record

    def audit_system_portfolio(
        self,
        current_portfolio_equity: float,
        state_pod_snapshots: Optional[List[Dict[str, Any]]] = None,
        returns_dict: Optional[Dict[str, pd.Series]] = None,
        mock_high_correlation_pairs: Optional[int] = None,
        now_utc: Optional[datetime] = None,
    ) -> SystemCircuitBreakerSnapshot:
        """
        Executes systemic portfolio audit across all 50 State Pods and global safety limits.
        """
        dt = now_utc or datetime.now(timezone.utc)
        if current_portfolio_equity > self.portfolio_peak_equity:
            self.portfolio_peak_equity = current_portfolio_equity

        port_dd = (self.portfolio_peak_equity - current_portfolio_equity) / self.portfolio_peak_equity
        port_dd_pct = round(port_dd * 100.0, 2)

        # 1. Nuclear Football Check (-7.5% System Portfolio Drawdown)
        if port_dd >= 0.075:
            self.nuclear_football_triggered = True
            logger.critical(
                f"🔥 [TÒA ÁN TỐI CAO - NUCLEAR FOOTBALL]: PORTFOLIO DRAWDOWN {port_dd_pct}% >= 7.5%! "
                f"KÍCH HOẠT LỆNH BÀI PHONG TỎA TỐI CAO: KHÓA ROUTER & PHẲNG TOÀN BỘ 50 TIỂU BANG!"
            )
        else:
            self.nuclear_football_triggered = False

        # 2. Pairwise Correlation Spike Check (Layer 5)
        c5_result = InstitutionalStatutoryRules.check_correlation_spike_circuit_breaker(
            returns_dict=returns_dict, mock_high_pairs_count=mock_high_correlation_pairs
        )
        corr_spike_triggered = not c5_result.is_compliant

        # 3. Audit individual state pods if snapshot provided
        if state_pod_snapshots:
            for pod in state_pod_snapshots:
                self.audit_and_enforce_state_pod(
                    state_id=pod["state_id"],
                    state_name=pod.get("state_name", pod["state_id"]),
                    primary_asset=pod.get("primary_asset", "UNKNOWN"),
                    allocated_capital=pod.get("allocated_capital", 200.0),
                    current_equity=pod.get("current_equity", 200.0),
                    peak_equity=pod.get("peak_equity", 200.0),
                )

        quarantined_count = sum(1 for r in self.quarantine_registry.values() if r.quarantine_status == "QUARANTINED")
        deleveraged_count = sum(1 for r in self.quarantine_registry.values() if r.quarantine_status == "DELEVERAGED_50")
        normal_count = sum(1 for r in self.quarantine_registry.values() if r.quarantine_status == "NORMAL")

        snapshot = SystemCircuitBreakerSnapshot(
            timestamp_utc=dt.isoformat(),
            total_portfolio_equity=current_portfolio_equity,
            peak_portfolio_equity=self.portfolio_peak_equity,
            portfolio_drawdown_pct=port_dd_pct,
            nuclear_football_triggered=self.nuclear_football_triggered,
            correlation_spike_triggered=corr_spike_triggered,
            active_quarantined_states_count=quarantined_count,
            active_deleveraged_states_count=deleveraged_count,
            active_normal_states_count=normal_count,
            quarantine_registry=self.quarantine_registry,
        )

        self._save_registry(snapshot)
        return snapshot

    def authorize_order_routing(
        self,
        state_id: str,
        target_asset: str,
        requested_lots: float,
        portfolio_equity: float,
        pod_equity: float,
        pod_peak_equity: float,
        socket_latency_ms: float = 45.0,
        slippage_points: float = 1.5,
        now_utc: Optional[datetime] = None,
    ) -> Tuple[bool, float, str]:
        """
        Final Judicial Authorization Check before routing an order to MT5.
        Returns (is_authorized, final_approved_lots, rationale).
        """
        # 1. Check Nuclear Football
        if self.nuclear_football_triggered:
            return False, 0.0, "REJECTED_NUCLEAR_FOOTBALL_SYSTEM_FROZEN"

        # 2. Check State Quarantine Registry Status
        pod_rec = self.quarantine_registry.get(state_id)
        if pod_rec and pod_rec.quarantine_status == "QUARANTINED":
            return False, 0.0, f"REJECTED_POD_QUARANTINED_{state_id}"

        # 3. Apply 6-Layer Statutory Defense
        pod_dd = (max(pod_equity, pod_peak_equity) - pod_equity) / max(1.0, pod_peak_equity)
        port_dd = (self.portfolio_peak_equity - portfolio_equity) / max(1.0, self.portfolio_peak_equity)

        approved, final_lots, checks = InstitutionalStatutoryRules.audit_pre_order_routing(
            target_asset=target_asset,
            requested_lots=requested_lots,
            current_inventory_lots=0.0,
            total_active_equity=portfolio_equity,
            socket_latency_ms=socket_latency_ms,
            slippage_points=slippage_points,
            pod_drawdown=pod_dd,
            portfolio_drawdown=port_dd,
            now_utc=now_utc,
        )

        if not approved:
            failed_reasons = [c.rejection_reason for c in checks if not c.is_compliant and c.rejection_reason]
            return False, 0.0, f"REJECTED_STATUTORY_RULE_{'|'.join(failed_reasons)}"

        # If State is in DELEVERAGED_50 mode -> apply 50% scale down
        if pod_rec and pod_rec.quarantine_status == "DELEVERAGED_50":
            final_lots = round(max(0.01, final_lots * 0.50), 2)
            return True, final_lots, f"APPROVED_DELEVERAGED_50_{final_lots}_LOTS"

        return True, final_lots, f"APPROVED_NORMAL_{final_lots}_LOTS"


def main():
    manager = SupremeCourtCircuitBreakerManager()
    
    # Run a diagnostic test simulation
    print("=" * 105)
    print(" 🦅 TÒA ÁN TỐI CAO - BỘ QUẢN TRỊ RỦI RO NGẮT MẠCH TỰ ĐỘNG (SUPREME COURT CIRCUIT BREAKER)")
    print("=" * 105)

    # Simulate 5 sample pods with varying drawdowns
    sample_pods = [
        {"state_id": "STATE_01", "state_name": "Gold Micro-Scalp", "primary_asset": "XAUUSDm", "allocated_capital": 500.0, "current_equity": 520.0, "peak_equity": 525.0},
        {"state_id": "STATE_22", "state_name": "GBP/USD Liquidity", "primary_asset": "GBPUSDm", "allocated_capital": 500.0, "current_equity": 485.0, "peak_equity": 500.0}, # -3.0% DD -> DELEVERAGED_50
        {"state_id": "STATE_05", "state_name": "Bitcoin Volatility", "primary_asset": "BTCUSDm", "allocated_capital": 100.0, "current_equity": 94.0, "peak_equity": 100.0},  # -6.0% DD -> QUARANTINED
        {"state_id": "STATE_33", "state_name": "GBP/CHF Macro", "primary_asset": "GBPCHFm", "allocated_capital": 600.0, "current_equity": 615.0, "peak_equity": 615.0},
    ]

    snapshot = manager.audit_system_portfolio(current_portfolio_equity=10_200.0, state_pod_snapshots=sample_pods)
    
    print(f" Thời gian thực thi              : {snapshot.timestamp_utc}")
    print(f" Tổng vốn danh mục (Equity)       : ${snapshot.total_portfolio_equity:,.2f} USD")
    print(f" Drawdown danh mục toàn hệ thống : {snapshot.portfolio_drawdown_pct}%")
    print(f" Kích hoạt Nuclear Football      : {snapshot.nuclear_football_triggered}")
    print(f" Kích hoạt Tương quan Spikes    : {snapshot.correlation_spike_triggered}")
    print("-" * 105)
    print(" 📋 TRẠNG THÁI CÁCH LY 50 TIỂU BANG:")
    for sid, rec in snapshot.quarantine_registry.items():
        print(f"  • {sid:<10} | {rec.primary_asset:<10} | DD: {rec.local_drawdown_pct:5.2f}% | Trạng thái: {rec.quarantine_status:<15} | CB Active: {rec.circuit_breaker_active}")

    # Test Order Authorization Routing
    print("-" * 105)
    print(" 🛡️ THỬ NGHIỆM PHÊ CHUẨN LỆNH GIAO DỊCH (JUDICIAL ORDER ROUTING AUDIT):")
    auth_gold, lots_gold, msg_gold = manager.authorize_order_routing("STATE_01", "XAUUSDm", 0.10, 10_200.0, 520.0, 525.0)
    print(f"  • STATE_01 (Gold Pod)   : Approved = {auth_gold} | Lots = {lots_gold} | Rationale: {msg_gold}")

    auth_gbp, lots_gbp, msg_gbp = manager.authorize_order_routing("STATE_22", "GBPUSDm", 0.10, 10_200.0, 485.0, 500.0)
    print(f"  • STATE_22 (Deleveraged): Approved = {auth_gbp} | Lots = {lots_gbp} | Rationale: {msg_gbp}")

    auth_btc, lots_btc, msg_btc = manager.authorize_order_routing("STATE_05", "BTCUSDm", 0.10, 10_200.0, 94.0, 100.0)
    print(f"  • STATE_05 (Quarantined): Approved = {auth_btc} | Lots = {lots_btc} | Rationale: {msg_btc}")
    print("=" * 105 + "\n")


if __name__ == "__main__":
    main()
