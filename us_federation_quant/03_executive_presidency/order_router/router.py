"""
The Executive Presidency: Order Router & Execution Management System (EMS)
Verifies Judicial Warrants, checks Nuclear Football state, applies Avellaneda-Stoikov skewing with OFI,
and slices volume via TWAP, VWAP, or Almgren-Chriss optimal trajectories.
Interfaces with Broker Bridge for MetaTrader 5 (MT5) execution.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from ..avellaneda_stoikov.engine import AvellanedaStoikovEngine
from ..nuclear_football_hardstop import NuclearFootball
from ..optimal_execution.almgren_chriss import AlmgrenChrissExecutor
from ..optimal_execution.vwap_profile import VWAPProfileSlicer
from ..optimal_execution.slippage_impact_model import SlippageImpactModel
from ..broker_bridge.mt5_payload_builder import MT5PayloadBuilder


class ExecutiveUnauthorizedError(Exception):
    """Raised when an order is attempted without a valid Supreme Court Warrant or while Nuclear Football is active."""
    pass


@dataclass
class MicroOrderSlice:
    """A sliced child order sent to liquidity pools."""
    slice_index: int
    total_slices: int
    asset: str
    action: str
    lots: float
    target_price: float
    order_type: str
    client_order_id: str = ""
    parent_warrant_id: Optional[str] = None


class ExecutiveOrderRouter:
    """
    Commander-in-Chief Central Execution Router.
    """

    def __init__(self, secret_key: str = "SUPREME_COURT_SEAL"):
        self.secret_key = secret_key
        self.nuclear_football = NuclearFootball()
        self.as_engine = AvellanedaStoikovEngine()
        self.ac_executor = AlmgrenChrissExecutor()
        self.vwap_slicer = VWAPProfileSlicer()
        self.slippage_model = SlippageImpactModel()
        self.mt5_builder = MT5PayloadBuilder()
        self.routed_history: List[Dict[str, Any]] = []

    def route_execution(
        self,
        warrant,
        market_mid_price: float = 2000.0,
        current_inventory: float = 0.0,
        volatility: float = 0.01,
        fed_quota: Optional[float] = None,
        slices: int = 5,
        execution_strategy: str = "TWAP",
        order_flow_imbalance: float = 0.0,
        daily_adv_lots: float = 10000.0
    ) -> List[MicroOrderSlice]:
        """
        Executes an authorized Judicial Warrant through micro-slices.

        :param warrant: JudicialWarrant signed by the Supreme Court
        :param market_mid_price: Current reference price
        :param current_inventory: Executive current net position
        :param volatility: Volatility estimate
        :param fed_quota: Federal Reserve balance sheet liquidity ceiling
        :param slices: Number of child order slices
        :param execution_strategy: "TWAP", "VWAP", or "ALMGREN_CHRISS"
        :param order_flow_imbalance: OFI in [-1.0, 1.0] for Avellaneda-Stoikov skew
        :param daily_adv_lots: Average Daily Volume for slippage & impact estimation
        :return: List of MicroOrderSlice objects
        """
        if self.nuclear_football.is_detonated:
            raise ExecutiveUnauthorizedError("EXECUTIVE HALT: The Nuclear Football has been detonated. All execution suspended.")

        # Verify Warrant authenticity
        if not hasattr(warrant, "verify_token") or not warrant.verify_token(self.secret_key):
            raise ExecutiveUnauthorizedError("UNCONSTITUTIONAL ATTEMPT: Invalid or missing Supreme Court signature token.")

        # Sizing governed by warrant and capped by FED Quota
        total_lots = warrant.authorized_lots
        if fed_quota is not None and fed_quota < total_lots:
            total_lots = fed_quota

        if total_lots <= 0:
            return []

        # Statutory Institutional Governance Check
        try:
            import importlib
            _inst_mod = importlib.import_module("us_federation_quant.institutional_governance_rules")
            InstitutionalStatutoryRules = _inst_mod.InstitutionalStatutoryRules
            approved, final_lots, checks = InstitutionalStatutoryRules.audit_pre_order_routing(
                target_asset=getattr(warrant, "target_asset", "UNKNOWN"),
                requested_lots=total_lots,
                current_inventory_lots=current_inventory,
                total_active_equity=10_000.0,
            )
            if not approved:
                failed = [c.details for c in checks if not c.is_compliant]
                raise ExecutiveUnauthorizedError(f"STATUTORY GOVERNANCE REJECTION: {'; '.join(failed)}")
            total_lots = final_lots
        except ImportError:
            pass

        # Microstructure quote calculation with Order Flow Imbalance
        quotes = self.as_engine.calculate_quotes(
            mid_price=market_mid_price,
            inventory_q=current_inventory,
            volatility_sigma=volatility,
            order_flow_imbalance=order_flow_imbalance
        )

        target_price = quotes["optimal_bid"] if warrant.action.upper() == "BUY" else quotes["optimal_ask"]

        strategy_upper = execution_strategy.upper()
        micro_orders: List[MicroOrderSlice] = []
        w_id = getattr(warrant, "warrant_id", "WAR")[:8]
        full_w_id = getattr(warrant, "warrant_id", None)

        if strategy_upper == "VWAP":
            vwap_slices = self.vwap_slicer.slice_order(total_lots=total_lots, n_slices=slices)
            for v_slice in vwap_slices:
                order = MicroOrderSlice(
                    slice_index=v_slice["step"],
                    total_slices=slices,
                    asset=warrant.target_asset,
                    action=warrant.action,
                    lots=v_slice["slice_lots"],
                    target_price=target_price,
                    order_type="LIMIT_SKEWED_VWAP",
                    client_order_id=f"VWAP-{w_id}-S{v_slice['step']}"[:31],
                    parent_warrant_id=full_w_id,
                )
                micro_orders.append(order)

        elif strategy_upper in ["ALMGREN_CHRISS", "ALMGREN_CHRISS_OPTIMAL"]:
            ac_schedule = self.ac_executor.calculate_trajectory(
                total_lots=total_lots,
                volatility_sigma=volatility,
                n_slices=slices
            )
            for ac_slice in ac_schedule:
                order = MicroOrderSlice(
                    slice_index=ac_slice["step"],
                    total_slices=slices,
                    asset=warrant.target_asset,
                    action=warrant.action,
                    lots=ac_slice["slice_lots"],
                    target_price=target_price,
                    order_type="LIMIT_SKEWED_ALMGREN_CHRISS",
                    client_order_id=f"AC-{w_id}-S{ac_slice['step']}"[:31],
                    parent_warrant_id=full_w_id,
                )
                micro_orders.append(order)

        else:
            # Default: TWAP equal lot distribution
            slice_lot = round(total_lots / slices, 2)
            # Ensure sum matches total_lots exactly
            allocated_lots = [slice_lot] * slices
            diff = round(total_lots - sum(allocated_lots), 2)
            if abs(diff) > 1e-4:
                allocated_lots[0] = round(allocated_lots[0] + diff, 2)

            for i in range(1, slices + 1):
                order = MicroOrderSlice(
                    slice_index=i,
                    total_slices=slices,
                    asset=warrant.target_asset,
                    action=warrant.action,
                    lots=allocated_lots[i - 1],
                    target_price=target_price,
                    order_type="LIMIT_SKEWED_TWAP",
                    client_order_id=f"TWAP-{w_id}-S{i}"[:31],
                    parent_warrant_id=full_w_id,
                )
                micro_orders.append(order)

        # Market impact estimation
        impact_analysis = self.slippage_model.estimate_impact(
            order_lots=total_lots,
            mid_price=market_mid_price,
            daily_adv_lots=daily_adv_lots,
            volatility_sigma=volatility
        )

        self.routed_history.append({
            "warrant_id": warrant.warrant_id,
            "asset": warrant.target_asset,
            "total_lots": total_lots,
            "strategy": strategy_upper,
            "slices": len(micro_orders),
            "quotes": quotes,
            "impact_analysis": impact_analysis
        })

        return micro_orders

    def handle_slice_failure(
        self,
        client_order_id: str,
        error_reason: str,
        reconciler: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Nautilus-inspired Quota Clawback & Failure Isolation:
        When a child slice fails (broker reject or slippage cap), aborts all
        subsequent pending slices under the parent warrant to stop cascading risk.
        """
        if reconciler is not None:
            return reconciler.handle_slice_failure(
                client_order_id=client_order_id,
                error_reason=error_reason,
                auto_clawback=True,
            )
        return {
            "failed_order_id": client_order_id,
            "reason": error_reason,
            "status": "SLICE_FAILED_NO_RECONCILER",
        }

    def to_mt5_requests(
        self,
        micro_orders: List[MicroOrderSlice],
        sl_price: float = 0.0,
        tp_price: float = 0.0,
        deviation_points: int = 15,
        magic_number: int = 20260919
    ) -> List[Dict[str, Any]]:
        """
        Translates a list of MicroOrderSlices into MT5 MqlTradeRequest payloads.
        """
        return self.mt5_builder.build_batch_requests(
            slice_orders=micro_orders,
            sl_price=sl_price,
            tp_price=tp_price,
            deviation_points=deviation_points,
            magic_number=magic_number
        )

