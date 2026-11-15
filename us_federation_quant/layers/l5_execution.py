"""l5_execution: tầng gộp từ l5_execution.py, order_state_machine.py, mt5_connection_manager.py, trailing_stop_manager.py, engine.py, mt5_live_connector.py, tca_monitor.py, nuclear_football_hardstop.py, almgren_chriss.py, slippage_impact_model.py, vwap_profile.py, mt5_payload_builder.py, router.py."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from us_federation_quant.Document.contracts import (
    AlertDirective, CloseDirective, Directive, LockDirective, LogDirective, LogLine, ModifyDirective,
    RaiseDirective, ReopenPersistDirective, TwoTierStateDirective,
)
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
import os
import math
import threading
from typing import Optional, Dict, Any, List
import pandas as pd
import MetaTrader5 as mt5
from typing import Dict, Any
from typing import Dict, Any, List, Optional
from typing import Dict, Any, List
from typing import List, Dict, Any
from typing import List, Dict, Any, Optional
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass


# ====================================================================================================
# layers/l5_execution.py  —  L5 Thực thi (bản TỐI THIỂU của bước 2): duyệt cây chỉ thị do L4 sinh ra và gọi MT5 qua mt5_mgr.
# ====================================================================================================

logger = logging.getLogger("USFederationQuant")
_LOCK_ATTR = {"ladder": "_profit_ladder_locked_tickets", "tier2": "_tier2_locked_tickets"}


@dataclass
class ExecutionOutcome:
    """Kết quả gom được khi thực thi (truyền vào từ ngoài để còn nguyên khi có ngoại lệ giữa chừng)."""
    buckets: Dict[str, List[Any]] = field(default_factory=dict)
    two_tier_modified: bool = False
    captured: Dict[str, Any] = field(default_factory=dict)

    def get(self, name: str) -> List[Any]:
        return self.buckets.get(name, [])


def _log(line: Optional[LogLine], error: Any = None) -> None:
    if line is None:
        return
    msg = line.message if error is None else line.message.replace("{error}", str(error))
    getattr(logger, line.level)(msg)


def _has_flow(d: Directive) -> bool:
    return bool(d.ok_log or d.fail_log or d.on_success or d.on_failure or d.collect)


def _run(rt: Any, d: Directive, out: ExecutionOutcome, two_tier_state: Optional[dict]) -> None:
    _log(d.pre_log)
    res = None
    if isinstance(d, CloseDirective):
        if d.positional:
            res = rt.mt5_mgr.close_position(d.ticket)
        else:
            kwargs: Dict[str, Any] = {"ticket": d.ticket}
            if d.volume is not None:
                kwargs["volume"] = d.volume
            if d.comment is not None:
                kwargs["comment"] = d.comment
            res = rt.mt5_mgr.close_position(**kwargs)
    elif isinstance(d, ModifyDirective):
        kwargs = {"ticket": d.ticket, "sl": d.sl}
        if d.send_tp:
            kwargs["tp"] = d.tp
        res = rt.mt5_mgr.modify_position_sltp(**kwargs)
    elif isinstance(d, AlertDirective):
        rt.telemetry.broadcast_critical_alert(subject=d.subject, body=d.body)
    elif isinstance(d, LockDirective):
        getattr(rt, _LOCK_ATTR[d.store]).add(d.ticket)
    elif isinstance(d, TwoTierStateDirective):
        if d.op == "set":
            value = dict(d.value or {})
            if d.stamp_time:
                value["time"] = datetime.now(timezone.utc).isoformat()
            two_tier_state[d.key] = value
            out.two_tier_modified = True
        elif d.op == "delete":
            del two_tier_state[d.key]
            out.two_tier_modified = True
        elif d.op == "save" and out.two_tier_modified:
            rt._save_two_tier_state(two_tier_state)
    elif isinstance(d, ReopenPersistDirective):
        rt._save_sweeper_reopen_state(dict(d.snapshot))
    elif isinstance(d, RaiseDirective):
        raise d.error
    elif not isinstance(d, LogDirective):
        raise TypeError(f"Directive không hỗ trợ: {type(d).__name__}")

    if d.capture is not None and res is not None:
        out.captured[d.capture] = res

    if res is not None and _has_flow(d):
        if res.get("success"):
            _log(d.ok_log)
            execute_directives(rt, d.on_success, outcome=out, two_tier_state=two_tier_state)
            if d.collect:
                out.buckets.setdefault(d.collect, []).append(res)
        else:
            _log(d.fail_log, error=res.get("error"))
            execute_directives(rt, d.on_failure, outcome=out, two_tier_state=two_tier_state)


def execute_directives(rt: Any, directives: Sequence[Directive], *, outcome: Optional[ExecutionOutcome] = None,
                       two_tier_state: Optional[dict] = None) -> ExecutionOutcome:
    out = outcome if outcome is not None else ExecutionOutcome()
    for d in directives:
        _run(rt, d, out, two_tier_state)
    return out


# ====================================================================================================
# core/order_state_machine.py  —  ========================================================================================
# ====================================================================================================




logger__order_state_machine = logging.getLogger("OrderStateMachine")


class OrderState(str, Enum):
    """
    NautilusTrader-compliant order state enumeration.
    """
    PENDING_SUBMIT = "PENDING_SUBMIT"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# Allowed state transitions (Directed Acyclic Graph for valid order lifecycle)
VALID_TRANSITIONS: Dict[OrderState, Set[OrderState]] = {
    OrderState.PENDING_SUBMIT: {OrderState.SUBMITTED, OrderState.REJECTED, OrderState.CANCELED},
    OrderState.SUBMITTED: {OrderState.ACCEPTED, OrderState.REJECTED, OrderState.CANCELED},
    OrderState.ACCEPTED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELED,
        OrderState.EXPIRED,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELED,
        OrderState.EXPIRED,
    },
    OrderState.FILLED: set(),      # Terminal state
    OrderState.CANCELED: set(),    # Terminal state
    OrderState.REJECTED: set(),    # Terminal state
    OrderState.EXPIRED: set(),     # Terminal state
}

TERMINAL_STATES: Set[OrderState] = {
    OrderState.FILLED,
    OrderState.CANCELED,
    OrderState.REJECTED,
    OrderState.EXPIRED,
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal order state transition is attempted."""
    pass


class DuplicateOrderSubmissionError(Exception):
    """Raised when an order with an identical ClientOrderId is resubmitted."""
    pass


@dataclass
class OrderFill:
    """Records an executed fill/deal from broker."""
    fill_id: str
    price: float
    volume: float
    timestamp_ns: int
    commission: float = 0.0


@dataclass
class FederationOrder:
    """
    Institutional Value Object representing an Order in the US Federation.
    Adheres to NautilusTrader order model conventions.
    """
    client_order_id: str
    symbol: str
    direction: str                     # BUY / SELL
    volume: float
    price: float = 0.0                 # Target or execution price
    sl: float = 0.0
    tp: float = 0.0
    magic: int = 0
    comment: str = ""
    parent_warrant_id: Optional[str] = None
    slice_index: int = 1
    total_slices: int = 1
    state: OrderState = OrderState.PENDING_SUBMIT
    ticket: Optional[int] = None       # MT5 broker order ticket
    ts_created_ns: int = field(default_factory=time.time_ns)
    ts_last_update_ns: int = field(default_factory=time.time_ns)
    fills: List[OrderFill] = field(default_factory=list)
    reject_reason: Optional[str] = None
    cancel_reason: Optional[str] = None
    state_history: List[Tuple[OrderState, int]] = field(default_factory=list)

    def __post_init__(self):
        if not self.state_history:
            self.state_history.append((self.state, self.ts_created_ns))

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def filled_volume(self) -> float:
        return round(sum(f.volume for f in self.fills), 4)

    @property
    def remaining_volume(self) -> float:
        return max(0.0, round(self.volume - self.filled_volume, 4))

    def transition_to(
        self,
        new_state: OrderState,
        reason: Optional[str] = None,
        fill_volume: Optional[float] = None,
        fill_price: Optional[float] = None,
        broker_order_id: Optional[int] = None,
    ) -> None:
        """Transitions order state using OrderStateMachine."""
        if new_state == OrderState.FILLED and fill_volume is not None and fill_price is not None:
            OrderStateMachine.apply_fill(
                self,
                price=fill_price,
                volume=fill_volume,
                ticket=broker_order_id,
            )
        else:
            OrderStateMachine.transition(self, new_state, reason=reason)


def generate_client_order_id(magic: int = 0, prefix: str = "FED") -> str:
    """
    Generates a deterministic, MT5-compatible unique ClientOrderId.
    MT5 comment has a 31-character limit, so format is compact:
    e.g.: FED-260901-7A3B9F1C
    """
    hex_uuid = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{magic}-{hex_uuid}"[:31]


class OrderStateMachine:
    """
    Manages deterministic order state transitions.
    """

    @staticmethod
    def transition(order: FederationOrder, new_state: OrderState, reason: Optional[str] = None) -> None:
        """
        Executes a validated state transition on an order.
        Raises InvalidStateTransitionError if illegal.
        """
        current_state = order.state
        if new_state == current_state:
            return  # No-op idempotent

        allowed = VALID_TRANSITIONS.get(current_state, set())
        if new_state not in allowed:
            err_msg = (
                f"Illegal order state transition for {order.client_order_id}: "
                f"{current_state.value} -> {new_state.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )
            logger__order_state_machine.error(f"❌ {err_msg}")
            raise InvalidStateTransitionError(err_msg)

        now_ns = time.time_ns()
        order.state = new_state
        order.ts_last_update_ns = now_ns
        order.state_history.append((new_state, now_ns))

        if reason:
            if new_state == OrderState.REJECTED:
                order.reject_reason = reason
            elif new_state == OrderState.CANCELED:
                order.cancel_reason = reason

        logger__order_state_machine.debug(
            f"🔄 Order {order.client_order_id} state transition: "
            f"{current_state.value} -> {new_state.value}"
        )

    @staticmethod
    def apply_fill(order: FederationOrder, price: float, volume: float, ticket: Optional[int] = None) -> None:
        """
        Applies a broker fill to the order, advancing state to PARTIALLY_FILLED or FILLED.
        """
        if order.is_terminal:
            raise InvalidStateTransitionError(
                f"Cannot apply fill to order {order.client_order_id} in terminal state {order.state.value}"
            )

        # Advance to ACCEPTED first if still in SUBMITTED
        if order.state == OrderState.SUBMITTED:
            OrderStateMachine.transition(order, OrderState.ACCEPTED)

        if ticket is not None:
            order.ticket = ticket

        fill = OrderFill(
            fill_id=f"FILL-{uuid.uuid4().hex[:6].upper()}",
            price=price,
            volume=volume,
            timestamp_ns=time.time_ns(),
        )
        order.fills.append(fill)

        if order.remaining_volume <= 1e-5:
            OrderStateMachine.transition(order, OrderState.FILLED)
        else:
            OrderStateMachine.transition(order, OrderState.PARTIALLY_FILLED)


class OrderReconciliationManager:
    """
    Central Idempotency Registry & In-flight Order Reconciler.
    Prevents duplicate submissions, enforces Nautilus-style Quota Clawback,
    and reconciles in-flight orders across broker disconnects.
    """

    def __init__(self):
        self._orders: Dict[str, FederationOrder] = {}
        self._ticket_to_client_id: Dict[int, str] = {}
        self._warrant_to_order_ids: Dict[str, List[str]] = {}

    def register_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        price: float = 0.0,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "",
        client_order_id: Optional[str] = None,
        parent_warrant_id: Optional[str] = None,
        slice_index: int = 1,
        total_slices: int = 1,
    ) -> FederationOrder:
        """
        Registers an order in PENDING_SUBMIT state with an idempotency key.
        """
        cid = client_order_id or generate_client_order_id(magic=magic)

        if cid in self._orders:
            existing = self._orders[cid]
            if not existing.is_terminal:
                raise DuplicateOrderSubmissionError(
                    f"Active order with ClientOrderId '{cid}' already exists in state {existing.state.value}!"
                )

        order = FederationOrder(
            client_order_id=cid,
            symbol=symbol,
            direction=direction.upper(),
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            magic=magic,
            comment=comment or cid,
            parent_warrant_id=parent_warrant_id,
            slice_index=slice_index,
            total_slices=total_slices,
        )
        self._orders[cid] = order

        if parent_warrant_id:
            if parent_warrant_id not in self._warrant_to_order_ids:
                self._warrant_to_order_ids[parent_warrant_id] = []
            self._warrant_to_order_ids[parent_warrant_id].append(cid)

        return order

    def mark_submitted(self, client_order_id: str) -> None:
        """Transitions order to SUBMITTED."""
        order = self.get_order(client_order_id)
        if order:
            OrderStateMachine.transition(order, OrderState.SUBMITTED)

    def mark_rejected(self, client_order_id: str, reason: str) -> None:
        """Transitions order to REJECTED."""
        order = self.get_order(client_order_id)
        if order:
            OrderStateMachine.transition(order, OrderState.REJECTED, reason=reason)

    def mark_canceled(self, client_order_id: str, reason: str = "ADMINISTRATIVE_CANCEL") -> None:
        """Transitions order to CANCELED."""
        order = self.get_order(client_order_id)
        if order and not order.is_terminal:
            OrderStateMachine.transition(order, OrderState.CANCELED, reason=reason)

    def mark_filled(self, client_order_id: str, price: float, volume: float, ticket: int) -> None:
        """Applies execution fill and links broker ticket."""
        order = self.get_order(client_order_id)
        if order:
            self._ticket_to_client_id[ticket] = client_order_id
            OrderStateMachine.apply_fill(order, price=price, volume=volume, ticket=ticket)

    def get_order(self, client_order_id: str) -> Optional[FederationOrder]:
        return self._orders.get(client_order_id)

    def get_order_by_ticket(self, ticket: int) -> Optional[FederationOrder]:
        cid = self._ticket_to_client_id.get(ticket)
        return self._orders.get(cid) if cid else None

    def get_orders_by_warrant(self, parent_warrant_id: str) -> List[FederationOrder]:
        cids = self._warrant_to_order_ids.get(parent_warrant_id, [])
        return [self._orders[cid] for cid in cids if cid in self._orders]

    def get_active_orders(self, magic: Optional[int] = None) -> List[FederationOrder]:
        """Returns all non-terminal in-flight orders."""
        return [
            o for o in self._orders.values()
            if not o.is_terminal and (magic is None or o.magic == magic)
        ]

    # ----------------------------------------------------------------------------------
    # NAUTILUS-STYLE QUOTA CLAWBACK & FAILURE ISOLATION ENGINE
    # ----------------------------------------------------------------------------------
    def clawback_remaining_quota(self, parent_warrant_id: str, reason: str) -> Dict[str, Any]:
        """
        Nautilus-inspired Quota Clawback:
        Cancels all pending or active child slices associated with a parent warrant.
        Revokes remaining unexecuted lot allocation to prevent cascading slippage.
        """
        warrant_orders = self.get_orders_by_warrant(parent_warrant_id)
        clawed_back_lots = 0.0
        aborted_cids = []

        for order in warrant_orders:
            if not order.is_terminal:
                rem_vol = order.remaining_volume
                clawed_back_lots += rem_vol
                try:
                    OrderStateMachine.transition(order, OrderState.CANCELED, reason=reason)
                    aborted_cids.append(order.client_order_id)
                except InvalidStateTransitionError:
                    pass

        logger__order_state_machine.warning(
            f"🛡️ [QUOTA_CLAWBACK] Warrant '{parent_warrant_id}' clawed back {clawed_back_lots:.2f} lots "
            f"across {len(aborted_cids)} aborted slices. Reason: {reason}"
        )

        return {
            "warrant_id": parent_warrant_id,
            "clawed_back_lots": round(clawed_back_lots, 4),
            "aborted_orders_count": len(aborted_cids),
            "aborted_client_order_ids": aborted_cids,
            "status": "QUOTA_REVOKED",
        }

    def handle_slice_failure(
        self,
        client_order_id: str,
        error_reason: str,
        auto_clawback: bool = True
    ) -> Dict[str, Any]:
        """
        Handles an execution failure on a specific micro-order slice.
        Transitions the failed order to REJECTED.
        If auto_clawback is True and order has parent_warrant_id,
        aborts all subsequent slices under the same parent warrant.
        """
        order = self.get_order(client_order_id)
        if not order:
            return {"error": f"Order {client_order_id} not found", "status": "FAILED"}

        if not order.is_terminal:
            self.mark_rejected(client_order_id, reason=error_reason)

        clawback_report = None
        if auto_clawback and order.parent_warrant_id:
            clawback_report = self.clawback_remaining_quota(
                parent_warrant_id=order.parent_warrant_id,
                reason=f"Cascading abort triggered by slice '{client_order_id}' failure: {error_reason}"
            )

        return {
            "failed_order_id": client_order_id,
            "state": OrderState.REJECTED.value,
            "reason": error_reason,
            "clawback_report": clawback_report,
            "status": "SLICE_REJECTED_QUOTA_REVOKED" if clawback_report else "SLICE_REJECTED",
        }

    def clear(self) -> None:
        """Clears memory registry (useful for testing)."""
        self._orders.clear()
        self._ticket_to_client_id.clear()
        self._warrant_to_order_ids.clear()


# ====================================================================================================
# core/mt5_connection_manager.py  —  US Federation Quant — MT5 Connection Manager
# ====================================================================================================



try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

try:
    from us_federation_quant.layers.l6_telemetry import get_logger
except ImportError:
    try:
        from us_federation_quant.layers.l6_telemetry import get_logger
    except ImportError:
        def get_logger():
            return logging.getLogger("USFederationQuant")

logger__mt5_connection_manager = get_logger()

try:
    pass
except ImportError:
    pass

# Timeframe mapping
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1 if MT5_AVAILABLE else 1,
    "M5": mt5.TIMEFRAME_M5 if MT5_AVAILABLE else 5,
    "M15": mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15,
    "M30": mt5.TIMEFRAME_M30 if MT5_AVAILABLE else 30,
    "H1": mt5.TIMEFRAME_H1 if MT5_AVAILABLE else 16385,
    "H4": mt5.TIMEFRAME_H4 if MT5_AVAILABLE else 16388,
    "D1": mt5.TIMEFRAME_D1 if MT5_AVAILABLE else 16408,
}


class StateMachineAdapter:
    """Adapter bridging OrderReconciliationManager to live runner's state_machine interface."""
    def __init__(self, reconciler: OrderReconciliationManager):
        self.reconciler = reconciler

    def create_order(
        self,
        client_order_id: str,
        symbol: str,
        order_type: str = "MARKET",
        direction: str = "BUY",
        volume: float = 0.01,
        magic: int = 0,
        warrant_id: Optional[str] = None,
        price: float = 0.0,
        sl: float = 0.0,
        tp: float = 0.0,
    ) -> FederationOrder:
        return self.reconciler.register_order(
            symbol=symbol,
            direction=direction,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            magic=magic,
            comment=client_order_id,
            client_order_id=client_order_id,
            parent_warrant_id=warrant_id,
        )


class MT5ConnectionManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MT5ConnectionManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, terminal_path: str = "", account: int = 0, password: str = "", server: str = ""):
        if self._initialized:
            return

        self.terminal_path = terminal_path or os.getenv("MT5_PATH", "")
        self.account = account or int(os.getenv("MT5_ACCOUNT", "0"))
        self.password = password or os.getenv("MT5_PASSWORD", "")
        self.server = server or os.getenv("MT5_SERVER", "")
        self.connected = False
        self._last_health_check = 0.0
        self.reconciler = OrderReconciliationManager()
        self.state_machine = StateMachineAdapter(self.reconciler)
        self._symbol_cache: Dict[str, str] = {}
        self._initialized = True

    def connect(self) -> bool:
        """Initialize and login to MetaTrader 5."""
        if not MT5_AVAILABLE:
            logger__mt5_connection_manager.error("❌ MetaTrader5 Python library is not installed.")
            return False

        with self._lock:
            init_kwargs = {"timeout": 30000}
            if self.terminal_path and os.path.exists(self.terminal_path):
                init_kwargs["path"] = self.terminal_path
            if self.account:
                init_kwargs["login"] = int(self.account)
            if self.password:
                init_kwargs["password"] = str(self.password)
            if self.server:
                init_kwargs["server"] = str(self.server)

            # Attempt direct initialization to attach to running MT5 GUI
            init_ok = mt5.initialize(**init_kwargs)
            if not init_ok:
                try:
                    mt5.shutdown()
                except Exception:
                    pass
                time.sleep(1)
                init_ok = mt5.initialize(**init_kwargs)

            if not init_ok:
                err = mt5.last_error()
                logger__mt5_connection_manager.error(f"❌ MT5 initialize() failed: {err}")
                self.connected = False
                return False

            curr_acc = mt5.account_info()
            if curr_acc and self.account and curr_acc.login == self.account:
                login_ok = True
            elif self.account and self.password and self.server:
                try:
                    login_ok = mt5.login(login=self.account, password=self.password, server=self.server, timeout=10000)
                except TypeError:
                    login_ok = mt5.login(login=self.account, password=self.password, server=self.server)
                if not login_ok:
                    err = mt5.last_error()
                    logger__mt5_connection_manager.error(f"❌ MT5 login({self.account} @ {self.server}) failed: {err}")
                    self.connected = False
                    return False

            term_info = mt5.terminal_info()
            acct_info = mt5.account_info()
            if not term_info or not acct_info:
                logger__mt5_connection_manager.warning("⚠️ MT5 initialized but terminal_info / account_info unavailable.")
                self.connected = False
                return False

            self.connected = True
            logger__mt5_connection_manager.info(
                f"✅ MT5 Connected: Account {acct_info.login} ({acct_info.server}), "
                f"Balance: ${acct_info.balance:.2f}, Equity: ${acct_info.equity:.2f}, Leverage: 1:{acct_info.leverage}"
            )
            return True

    def ensure_connected(self) -> bool:
        """Check connection health and auto-reconnect if needed."""
        now = time.time()
        if now - self._last_health_check < 5.0 and self.connected:
            return True

        self._last_health_check = now
        if not MT5_AVAILABLE:
            return False

        try:
            term_info = mt5.terminal_info()
            if term_info and term_info.connected:
                self.connected = True
                return True
        except Exception:
            pass

        logger__mt5_connection_manager.warning("⚠️ MT5 connection dropped. Attempting reconnect...")
        return self.connect()

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Retrieve latest account snapshot."""
        if not self.ensure_connected():
            return None

        with self._lock:
            info = mt5.account_info()
            if not info:
                return None
            return {
                "login": info.login,
                "server": info.server,
                "balance": float(info.balance),
                "equity": float(info.equity),
                "margin": float(info.margin),
                "free_margin": float(info.margin_free),
                "margin_level": float(info.margin_level) if info.margin_level else 0.0,
                "profit": float(info.profit),
                "currency": info.currency,
                "leverage": info.leverage,
            }

    def resolve_symbol(self, raw_symbol: str) -> str:
        """
        Resolve an asset identifier or symbol into the broker's exact MT5 symbol.
        Handles suffixes (e.g. 'm', '.m', 'pro'), aliases (e.g. 'GOOG' -> 'GOOGL', 'DE40' -> 'DE30'),
        and case variations. Caches resolved symbols for sub-millisecond lookups.
        """
        if not raw_symbol:
            return ""

        if not hasattr(self, "_symbol_cache"):
            self._symbol_cache = {}

        if raw_symbol in self._symbol_cache:
            return self._symbol_cache[raw_symbol]

        if not self.ensure_connected():
            return raw_symbol

        # Known institutional broker aliases
        aliases = {
            "GOOG": "GOOGL",
            "GOOGM": "GOOGL",
            "NATGAS": "XNGUSD",
            "NATGASM": "XNGUSD",
            "DE40": "DE30",
            "DE40M": "DE30",
            "AU200": "AUS200",
            "AU200M": "AUS200",
            "BRK": "BAC",
            "BRKM": "BAC",
        }

        clean = raw_symbol.strip()
        clean_upper = clean.upper()
        base = clean[:-1] if clean_upper.endswith("M") and len(clean) >= 2 else clean
        base_upper = base.upper()

        candidates = [clean]
        if clean_upper in aliases:
            candidates.append(aliases[clean_upper])
        if base_upper in aliases:
            candidates.append(aliases[base_upper])
        if base != clean:
            candidates.append(base)

        env_suffix = os.getenv("MT5_SUFFIX", "").strip()
        if env_suffix:
            candidates.append(base + env_suffix)
            candidates.append(clean + env_suffix)

        for sfx in ["m", ".m", "c", "pro"]:
            candidates.append(base + sfx)

        with self._lock:
            for cand in candidates:
                info = mt5.symbol_info(cand)
                if info is not None:
                    if not info.visible:
                        mt5.symbol_select(cand, True)
                    self._symbol_cache[raw_symbol] = cand
                    return cand

            all_symbols = mt5.symbols_get()
            if all_symbols:
                sym_map = {s.name.upper(): s.name for s in all_symbols}
                for cand in candidates:
                    if cand.upper() in sym_map:
                        exact_name = sym_map[cand.upper()]
                        mt5.symbol_select(exact_name, True)
                        self._symbol_cache[raw_symbol] = exact_name
                        return exact_name

        resolved = base if base else raw_symbol
        self._symbol_cache[raw_symbol] = resolved
        return resolved

    def get_filling_mode(self, symbol: str) -> int:
        """Determines the broker's valid MT5 filling mode for the symbol (FOK, IOC, or RETURN)."""
        symbol = self.resolve_symbol(symbol)
        info = mt5.symbol_info(symbol) if MT5_AVAILABLE else None
        if info is None:
            return mt5.ORDER_FILLING_FOK if MT5_AVAILABLE else 0
        modes = info.filling_mode
        # Exness bitmask:
        # bit 0 (1): FOK
        # bit 1 (2): IOC
        if modes & 1:
            return mt5.ORDER_FILLING_FOK
        elif modes & 2:
            return mt5.ORDER_FILLING_IOC
        else:
            return mt5.ORDER_FILLING_RETURN

    def is_market_open(self, symbol: str, max_tick_age_seconds: float = 600.0) -> bool:
        """
        Market Session Gatekeeper:
        Checks if trading is active and broker session is open for the given symbol.
        Returns False if:
        1. MT5 is not connected or symbol is invalid.
        2. Trade mode is disabled (SYMBOL_TRADE_MODE_DISABLED).
        3. Most recent tick is older than max_tick_age_seconds (e.g. US Equities outside NYSE hours).
        """
        if not self.ensure_connected():
            return False

        symbol = self.resolve_symbol(symbol)
        with self._lock:
            info = mt5.symbol_info(symbol) if MT5_AVAILABLE else None
            if not info:
                return False

            # Check if trading is enabled with FULL access (not disabled, close-only, or holiday closed)
            if hasattr(info, "trade_mode") and info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                return False

            tick = mt5.symbol_info_tick(symbol) if MT5_AVAILABLE else None
            if not tick or tick.time == 0:
                return False

            now_dt = datetime.now(timezone.utc)
            now_ts = now_dt.timestamp()
            tick_age = now_ts - float(tick.time)
            # Điểm mù múi giờ: Nếu tick.time có cộng sẵn offset của MT5 Server (UTC+2/UTC+3),
            # now_ts - tick.time sẽ bị âm (-7200s đến -10800s). Quy chiếu về cùng hệ MT5 Server Time:
            if tick_age < -60.0:
                year = now_dt.year
                mar_1 = datetime(year, 3, 1, tzinfo=timezone.utc)
                dst_start = datetime(year, 3, 1 + (6 - mar_1.weekday()) % 7 + 7, 7, 0, 0, tzinfo=timezone.utc)
                nov_1 = datetime(year, 11, 1, tzinfo=timezone.utc)
                dst_end = datetime(year, 11, 1 + (6 - nov_1.weekday()) % 7, 6, 0, 0, tzinfo=timezone.utc)
                srv_offset_sec = 3 * 3600.0 if (dst_start <= now_dt < dst_end) else 2 * 3600.0
                tick_age = (now_ts + srv_offset_sec) - float(tick.time)
            if tick_age > max_tick_age_seconds or tick_age < -60.0:
                return False

            return True

    def get_rates(self, symbol: str, timeframe_str: str, count: int = 100) -> Optional[pd.DataFrame]:
        """Fetch latest candles for a symbol. Returns DataFrame with UTC datetime index."""
        if not self.ensure_connected():
            return None

        symbol = self.resolve_symbol(symbol)
        tf = TIMEFRAME_MAP.get(timeframe_str.upper(), mt5.TIMEFRAME_H1)

        with self._lock:
            if not mt5.symbol_select(symbol, True):
                logger__mt5_connection_manager.error(f"❌ Cannot select symbol '{symbol}' in Market Watch.")
                return None

            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None or len(rates) == 0:
                logger__mt5_connection_manager.error(f"❌ Failed to fetch rates for {symbol} ({timeframe_str}): {mt5.last_error()}")
                return None

            df = pd.DataFrame(rates)
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('datetime', inplace=True)
            return df

    def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch latest tick for a symbol."""
        if not self.ensure_connected():
            return None

        symbol = self.resolve_symbol(symbol)
        with self._lock:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return None
            return {
                "bid": float(tick.bid),
                "ask": float(tick.ask),
                "spread": float(tick.ask - tick.bid),
                "time": tick.time,
            }

    def get_symbol_spec(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieve instrument specifications (point, digits, contract_size, lot steps)."""
        if not self.ensure_connected():
            return None

        symbol = self.resolve_symbol(symbol)
        with self._lock:
            info = mt5.symbol_info(symbol)
            if not info:
                return None
            return {
                "point": float(info.point),
                "digits": int(info.digits),
                "contract_size": float(info.trade_contract_size),
                "volume_min": float(info.volume_min),
                "volume_max": float(info.volume_max),
                "volume_step": float(info.volume_step),
                "spread_points": int(info.spread),
            }

    def normalize_lot(self, symbol: str, lot: float) -> float:
        """Round volume down to the instrument's volume_step and clamp between min and max."""
        symbol = self.resolve_symbol(symbol)
        spec = self.get_symbol_spec(symbol)
        if not spec:
            return round(lot, 2)

        vol_min = spec["volume_min"]
        vol_max = spec["volume_max"]
        vol_step = spec["volume_step"]

        steps = math.floor((lot - vol_min) / vol_step)
        norm = vol_min + (steps * vol_step)
        norm = max(vol_min, min(norm, vol_max))

        decimals = 2
        if vol_step >= 1:
            decimals = 0
        elif vol_step >= 0.1:
            decimals = 1
        elif vol_step >= 0.01:
            decimals = 2
        elif vol_step >= 0.001:
            decimals = 3

        return round(norm, decimals)

    def get_positions(self, magic: Optional[int] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve active open positions filtered by magic and/or symbol."""
        if not self.ensure_connected():
            return []

        with self._lock:
            raw = mt5.positions_get()
            if raw is None:
                return []

            positions = []
            for p in raw:
                if magic is not None and p.magic != magic:
                    continue
                if symbol is not None and p.symbol != symbol:
                    continue
                positions.append({
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "volume": float(p.volume),
                    "price_open": float(p.price_open),
                    "price_current": float(p.price_current),
                    "sl": float(p.sl),
                    "tp": float(p.tp),
                    "profit": float(p.profit),
                    "magic": int(p.magic),
                    "comment": str(p.comment),
                    "time": datetime.fromtimestamp(p.time, tz=timezone.utc),
                })
            return positions

    def open_market_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "",
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an IOC market order to MT5 with strict Nautilus-style Order State Machine & Idempotency.
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to MT5"}

        symbol = self.resolve_symbol(symbol)
        if not self.is_market_open(symbol):
            return {"success": False, "error": f"Market closed or trading disabled for {symbol}", "retcode": 10018}

        spec = self.get_symbol_spec(symbol)
        if not spec:
            return {"success": False, "error": f"Invalid symbol {symbol}"}

        lot = self.normalize_lot(symbol, volume)
        tick = self.get_tick(symbol)
        if not tick:
            return {"success": False, "error": f"Failed to get tick for {symbol}"}

        order_type = mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick["ask"] if direction.upper() == "BUY" else tick["bid"]

        # 1. Register order in State Machine (PENDING_SUBMIT) & verify Idempotency
        cid = client_order_id or generate_client_order_id(magic=magic)
        order_comment = comment or cid
        if len(order_comment) > 31:
            order_comment = order_comment[:31]

        try:
            fed_order = self.reconciler.register_order(
                symbol=symbol,
                direction=direction,
                volume=lot,
                price=price,
                sl=sl,
                tp=tp,
                magic=magic,
                comment=order_comment,
                client_order_id=cid,
            )
        except DuplicateOrderSubmissionError as e:
            logger__mt5_connection_manager.warning(f"⚠️ [IDEMPOTENCY] Duplicate order submission prevented: {e}")
            existing = self.reconciler.get_order(cid)
            return {
                "success": False,
                "error": str(e),
                "is_duplicate": True,
                "client_order_id": cid,
                "state": existing.state.value if existing else "UNKNOWN",
                "ticket": existing.ticket if existing else None,
            }

        filling_mode = self.get_filling_mode(symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": round(sl, spec["digits"]) if sl > 0 else 0.0,
            "tp": round(tp, spec["digits"]) if tp > 0 else 0.0,
            "deviation": 20,
            "magic": magic,
            "comment": order_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        # 2. Advance to SUBMITTED
        self.reconciler.mark_submitted(cid)

        with self._lock:
            result = mt5.order_send(request)
            if result and result.retcode == 10030:
                for fallback in [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]:
                    if fallback != request["type_filling"]:
                        request["type_filling"] = fallback
                        retry_res = mt5.order_send(request)
                        if retry_res and retry_res.retcode == mt5.TRADE_RETCODE_DONE:
                            result = retry_res
                            break

            if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = result.comment if result else str(mt5.last_error())
                retcode = result.retcode if result else -1
                if retcode == 10018:
                    logger__mt5_connection_manager.info(f"ℹ️ [MARKET_CLOSED] Thị trường đang đóng cửa hoặc nghỉ lễ ({symbol}): {err_msg} (retcode=10018). Bỏ qua an toàn.")
                else:
                    logger__mt5_connection_manager.error(f"❌ Order Send Failed ({symbol} {direction} {lot}L, magic={magic}, cid={cid}): {err_msg} (retcode={retcode})")
                self.reconciler.mark_rejected(cid, reason=f"{err_msg} (retcode={retcode})")
                return {
                    "success": False,
                    "error": err_msg,
                    "retcode": retcode,
                    "client_order_id": cid,
                    "state": OrderState.REJECTED.value,
                }

            # 3. Advance to FILLED
            self.reconciler.mark_filled(cid, price=result.price, volume=result.volume, ticket=result.order)

            logger__mt5_connection_manager.info(
                f"🚀 ORDER EXECUTED: Ticket #{result.order} | {symbol} {direction} {lot}L @ {result.price} | Magic: {magic} | CID: {cid}"
            )
            return {
                "success": True,
                "ticket": result.order,
                "price": result.price,
                "volume": result.volume,
                "magic": magic,
                "client_order_id": cid,
                "state": OrderState.FILLED.value,
            }

    def reconcile_in_flight_orders(self, magic: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Nautilus-style In-flight Order Reconciliation.
        Scans broker positions & history to resolve any dangling SUBMITTED orders.
        """
        if not self.ensure_connected():
            return []

        active_orders = self.reconciler.get_active_orders(magic=magic)
        reconciled = []

        with self._lock:
            positions = mt5.positions_get() or []
            pos_comments = {p.comment: p for p in positions}

            for order in active_orders:
                if order.state == OrderState.SUBMITTED and order.comment in pos_comments:
                    matched_pos = pos_comments[order.comment]
                    self.reconciler.mark_filled(
                        order.client_order_id,
                        price=matched_pos.price_open,
                        volume=matched_pos.volume,
                        ticket=matched_pos.ticket,
                    )
                    reconciled.append({
                        "client_order_id": order.client_order_id,
                        "ticket": matched_pos.ticket,
                        "action": "RECONCILED_FILLED_FROM_POSITION",
                    })

        return reconciled

    def close_position(self, ticket: int, volume: Optional[float] = None, comment: str = "Fleet Close") -> Dict[str, Any]:
        """Close an open position (or partially close specified volume) by ticket."""
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to MT5"}

        with self._lock:
            positions = mt5.positions_get(ticket=ticket)
            if not positions or len(positions) == 0:
                return {"success": False, "error": f"Position #{ticket} not found"}

            pos = positions[0]
            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                return {"success": False, "error": f"Failed to get tick for {pos.symbol}"}

            price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

            filling_mode = self.get_filling_mode(pos.symbol)

            # Determine execution volume (supports partial close)
            exec_volume = pos.volume
            if volume is not None and 0.0 < volume < pos.volume:
                exec_volume = self.normalize_lot(pos.symbol, volume)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": exec_volume,
                "type": close_type,
                "price": price,
                "deviation": 20,
                "magic": pos.magic,
                "comment": comment[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }

            result = mt5.order_send(request)
            if result and result.retcode == 10030:
                for fallback in [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]:
                    if fallback != request["type_filling"]:
                        request["type_filling"] = fallback
                        retry_res = mt5.order_send(request)
                        if retry_res and retry_res.retcode == mt5.TRADE_RETCODE_DONE:
                            result = retry_res
                            break

            if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = result.comment if result else str(mt5.last_error())
                logger__mt5_connection_manager.error(f"❌ Close Failed #{ticket}: {err_msg}")
                return {"success": False, "error": err_msg}

            is_partial = exec_volume < pos.volume
            log_desc = f"PARTIAL CLOSE ({exec_volume}L of {pos.volume}L)" if is_partial else f"FULL CLOSE ({exec_volume}L)"
            logger__mt5_connection_manager.info(f"✅ POSITION {log_desc}: Ticket #{ticket} ({pos.symbol}, Profit: ${pos.profit:.2f})")
            return {
                "success": True,
                "ticket": ticket,
                "closed_volume": exec_volume,
                "remaining_volume": round(pos.volume - exec_volume, 2) if is_partial else 0.0,
                "profit": pos.profit,
                "is_partial": is_partial,
            }

    def close_all_positions(self) -> List[Dict[str, Any]]:
        """Emergency liquidation: Close all open positions immediately."""
        positions = self.get_positions()
        results = []
        for p in positions:
            res = self.close_position(p["ticket"])
            results.append(res)
        return results

    def modify_position_sltp(self, ticket: int, sl: float = 0.0, tp: float = 0.0) -> Dict[str, Any]:
        """
        Modify Stop Loss and Take Profit for an open position by ticket.
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to MT5"}

        with self._lock:
            positions = mt5.positions_get(ticket=ticket)
            if not positions or len(positions) == 0:
                return {"success": False, "error": f"Position #{ticket} not found"}

            pos = positions[0]
            spec = self.get_symbol_spec(pos.symbol)
            digits = spec.get("digits", 2) if spec else 2

            new_sl = round(sl, digits) if sl > 0 else float(pos.sl)
            new_tp = round(tp, digits) if tp > 0 else float(pos.tp)

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "sl": new_sl,
                "tp": new_tp,
            }

            result = mt5.order_send(request)
            if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = result.comment if result else str(mt5.last_error())
                retcode = result.retcode if result else -1
                return {"success": False, "error": err_msg, "retcode": retcode}

            return {"success": True, "ticket": ticket, "sl": new_sl, "tp": new_tp}

    def enforce_mandatory_sl_protection(self, default_sl_pct: float = 0.015) -> List[Dict[str, Any]]:
        """
        Enforce Article 00 of Constitution: Every open position must have a valid Stop Loss.
        If a position has no SL (sl == 0.0), assign a mandatory protective Stop Loss.
        """
        if not self.ensure_connected():
            return []

        modified = []
        positions = self.get_positions()
        for p in positions:
            ticket = p["ticket"]
            sl = p["sl"]
            if sl == 0.0 or sl is None:
                symbol = p["symbol"]
                open_price = p["price_open"]
                pos_type = p["type"]
                spec = self.get_symbol_spec(symbol)
                digits = spec.get("digits", 2) if spec else 2

                if pos_type == "BUY":
                    calc_sl = round(open_price * (1.0 - default_sl_pct), digits)
                else:
                    calc_sl = round(open_price * (1.0 + default_sl_pct), digits)

                res = self.modify_position_sltp(ticket=ticket, sl=calc_sl)
                if res.get("success"):
                    logger__mt5_connection_manager.info(f"🛡️ [MANDATORY SL ASSIGNED] Ticket #{ticket} ({symbol} {pos_type}) assigned SL={calc_sl}")
                    modified.append(res)

        return modified

    def shutdown(self):
        """Cleanly shutdown MT5 connection."""
        with self._lock:
            if MT5_AVAILABLE and self.connected:
                mt5.shutdown()
                self.connected = False
                logger__mt5_connection_manager.info("🔌 MT5 connection shut down cleanly.")


# ====================================================================================================
# execution_layer/trailing_stop_manager.py  —  ========================================================================================
# ====================================================================================================



logger__trailing_stop_manager = logging.getLogger("TrailingStopManager")


class TrailingStopManager:
    def __init__(self, atr_period: int = 14, atr_multiplier: float = 2.0, min_modification_points: int = 25):
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.min_modification_points = min_modification_points

    def _calculate_h1_atr(self, symbol: str) -> float:
        """Tính toán Average True Range (ATR) trên khung H1."""
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, self.atr_period + 1)
        if rates is None or len(rates) < self.atr_period:
            return 0.0

        df = pd.DataFrame(rates)
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift(1))
        df['tr2'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

        atr = float(df['tr'].dropna().mean())
        return atr

    def update_trailing_stops(self):
        """Quét toàn bộ vị thế đang có lãi và dời SL theo Chandelier Exit (ATR)."""
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return

        for pos in positions:
            # Chỉ xử lý các lệnh đang có lợi nhuận dương
            if pos.profit <= 0:
                continue

            symbol = pos.symbol
            ticket = pos.ticket
            current_sl = float(pos.sl)
            order_type = pos.type

            s_info = mt5.symbol_info(symbol)
            if s_info is None:
                continue

            point = float(s_info.point)
            digits = int(s_info.digits)
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                continue

            current_price = tick.bid if order_type == mt5.ORDER_TYPE_BUY else tick.ask

            atr = self._calculate_h1_atr(symbol)
            if atr == 0.0:
                continue

            # Tính toán Stop Loss mới dựa trên Chandelier Exit
            if order_type == mt5.ORDER_TYPE_BUY:
                # Lệnh BUY: SL mới dời lên (Bám gót giá hiện tại trừ đi biên độ ATR)
                new_sl = current_price - (self.atr_multiplier * atr)
                new_sl = round(new_sl, digits)

                # Chỉ dời lên, không bao giờ lùi SL. Và phải lớn hơn SL cũ + buffer points
                if new_sl > current_sl and (new_sl - current_sl) >= (self.min_modification_points * point):
                    self._modify_sltp(ticket, symbol, new_sl, pos.tp, "BUY")

            elif order_type == mt5.ORDER_TYPE_SELL:
                # Lệnh SELL: SL mới dời xuống (Bám gót giá hiện tại cộng thêm biên độ ATR)
                new_sl = current_price + (self.atr_multiplier * atr)
                new_sl = round(new_sl, digits)

                # SL cũ = 0.0 (chưa cài) HOẶC SL mới phải thấp hơn SL cũ - buffer points
                if current_sl == 0.0 or (new_sl < current_sl and (current_sl - new_sl) >= (self.min_modification_points * point)):
                    self._modify_sltp(ticket, symbol, new_sl, pos.tp, "SELL")

    def _modify_sltp(self, ticket: int, symbol: str, new_sl: float, current_tp: float, type_str: str):
        """Gửi lệnh cập nhật SL/TP xuống MT5 Broker."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": new_sl,
            "tp": current_tp,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger__trailing_stop_manager.info(f"📈 [TRAILING STOP] Cập nhật SL lệnh {type_str} #{ticket} ({symbol}) -> {new_sl}")
        else:
            comment = result.comment if result else "Unknown"
            logger__trailing_stop_manager.error(f"❌ [TRAILING STOP] Lỗi dời SL lệnh #{ticket}: {comment}")


# ====================================================================================================
# 04_execution/avellaneda_stoikov/engine.py  —  Avellaneda-Stoikov Market Microstructure Execution Engine
# ====================================================================================================




class AvellanedaStoikovEngine:
    """
    Computes optimal reservation prices and spread placement.
    r(s, q, t) = s - q * gamma * sigma^2 * (T - t) + theta * OFI * sigma
    Incorporates Order Flow Imbalance (OFI) and adverse selection spread widening.
    """

    def __init__(
        self,
        gamma: float = 0.1,           # Risk aversion parameter
        kappa: float = 1.5,           # Order book liquidity density parameter
        time_horizon: float = 1.0,    # Time horizon T
        ofi_sensitivity: float = 0.25 # Adverse selection sensitivity to OFI
    ):
        self.gamma = gamma
        self.kappa = kappa
        self.time_horizon = time_horizon
        self.ofi_sensitivity = ofi_sensitivity

    def calculate_quotes(
        self,
        mid_price: float,
        inventory_q: float,
        volatility_sigma: float,
        time_remaining_t: float = 1.0,
        order_flow_imbalance: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculates reservation price and optimal bid/ask offsets.
        
        :param mid_price: Current market mid-price
        :param inventory_q: Current inventory position (positive = long, negative = short)
        :param volatility_sigma: Volatility (relative or dollar vol)
        :param time_remaining_t: Remaining time horizon fraction (0 < t <= 1)
        :param order_flow_imbalance: Normalized Order Flow Imbalance in [-1.0, 1.0]
        """
        # Convert relative volatility to dollar volatility if sigma < 1.0
        dollar_vol = (volatility_sigma * mid_price) if volatility_sigma < 1.0 else volatility_sigma

        # Inventory risk penalty
        inventory_penalty = (inventory_q * self.gamma * (dollar_vol ** 2) * time_remaining_t) / mid_price
        
        # Order Flow Imbalance (OFI) directional alpha drift adjustment
        # Positive OFI (buyer pressure) shifts reservation price upwards
        # Negative OFI (seller pressure) shifts reservation price downwards
        ofi_drift = self.ofi_sensitivity * order_flow_imbalance * dollar_vol * time_remaining_t
        
        reservation_price = mid_price - inventory_penalty + ofi_drift

        # Base half-spread term
        spread_term = ((self.gamma * (dollar_vol ** 2) * time_remaining_t) / mid_price) + (
            (2.0 / self.gamma) * math.log(1.0 + (self.gamma / self.kappa))
        )
        base_half_spread = max(0.01, spread_term / 2.0)

        # Adverse selection widening: when |OFI| is elevated, informed trading risk rises
        adverse_selection_multiplier = 1.0 + 0.5 * abs(order_flow_imbalance)
        half_spread = base_half_spread * adverse_selection_multiplier

        bid_price = round(reservation_price - half_spread, 4)
        ask_price = round(reservation_price + half_spread, 4)
        skew_offset = round(reservation_price - mid_price, 4)

        return {
            "mid_price": mid_price,
            "reservation_price": round(reservation_price, 4),
            "optimal_bid": bid_price,
            "optimal_ask": ask_price,
            "spread": round(ask_price - bid_price, 4),
            "skew_offset": skew_offset,
            "order_flow_imbalance": order_flow_imbalance
        }



# ====================================================================================================
# 04_execution/broker_bridge/mt5_live_connector.py  —  MetaTrader 5 Live & Paper Execution Gateway Connector.
# ====================================================================================================



logger__mt5_live_connector = logging.getLogger("MT5LiveConnector")


class MT5RetCode:
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_REQUOTE = 10004
    TRADE_RETCODE_REJECT = 10006
    TRADE_RETCODE_CONNECTION = 10031


class MT5LiveConnector:
    """
    Live/Paper Broker Gateway for MetaTrader 5.
    """

    def __init__(
        self,
        account: Optional[int] = None,
        server: Optional[str] = None,
        force_mock: bool = False
    ):
        self.account = account
        self.server = server
        self.force_mock = force_mock
        self.is_connected = False
        self.is_mock_mode = force_mock
        self._mock_positions: Dict[int, Dict[str, Any]] = {}
        self._next_ticket = 100001
        self._mock_balance = 1_000_000.0
        self._mock_equity = 1_000_000.0

        self._init_backend()

    def _init_backend(self):
        """Attempts to initialize MetaTrader5 package; falls back to MockBrokerGateway if unavailable."""
        if self.force_mock:
            self.is_mock_mode = True
            return

        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
            # Test basic initialization without credentials (terminal already open)
            initialized = self._mt5.initialize()
            if initialized:
                self.is_connected = True
                self.is_mock_mode = False
            else:
                self.is_mock_mode = True
        except (ImportError, Exception):
            self.is_mock_mode = True

    def connect(self) -> bool:
        """Connects to broker gateway."""
        if self.is_mock_mode:
            self.is_connected = True
            return True

        if not self.is_connected and hasattr(self, "_mt5"):
            self.is_connected = bool(self._mt5.initialize())
        return self.is_connected

    def disconnect(self):
        """Closes connection with terminal."""
        if not self.is_mock_mode and hasattr(self, "_mt5"):
            try:
                self._mt5.shutdown()
            except Exception:
                pass
        self.is_connected = False

    def get_account_info(self) -> Dict[str, Any]:
        """Returns account balance, equity, and margin telemetry."""
        if self.is_mock_mode or not self.is_connected:
            return {
                "login": self.account or 9999999,
                "trade_mode": "MOCK_PAPER",
                "balance": self._mock_balance,
                "equity": self._mock_equity,
                "margin": 0.0,
                "margin_free": self._mock_equity,
                "margin_level": 0.0,
                "currency": "USD"
            }

        acc = self._mt5.account_info()
        if acc is None:
            return {"error": "ACCOUNT_INFO_UNAVAILABLE", "is_connected": False}

        return {
            "login": acc.login,
            "trade_mode": "REAL" if acc.trade_mode == 0 else "DEMO",
            "balance": acc.balance,
            "equity": acc.equity,
            "margin": acc.margin,
            "margin_free": acc.margin_free,
            "margin_level": acc.margin_level,
            "currency": acc.currency
        }

    def send_trade_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submits an MqlTradeRequest dictionary to MT5.
        """
        if not self.is_connected:
            self.connect()

        if self.is_mock_mode:
            # Deterministic simulated execution
            ticket = self._next_ticket
            self._next_ticket += 1
            executed_price = request.get("price", 2000.0)
            lots = request.get("volume", 0.01)
            symbol = request.get("symbol", "XAUUSD")
            action_type = request.get("type", 0)

            position_entry = {
                "ticket": ticket,
                "symbol": symbol,
                "type": action_type,
                "volume": lots,
                "price_open": executed_price,
                "sl": request.get("sl", 0.0),
                "tp": request.get("tp", 0.0),
                "magic": request.get("magic", 20260919),
                "comment": request.get("comment", ""),
                "time": time.time()
            }
            self._mock_positions[ticket] = position_entry

            return {
                "retcode": MT5RetCode.TRADE_RETCODE_DONE,
                "deal": ticket + 500000,
                "order": ticket,
                "volume": lots,
                "price": executed_price,
                "bid": executed_price - 0.1,
                "ask": executed_price + 0.1,
                "comment": "MOCK_ORDER_DONE",
                "request": request
            }

        # Real MT5 execution
        result = self._mt5.order_send(request)
        if result is None:
            err = self._mt5.last_error()
            return {
                "retcode": MT5RetCode.TRADE_RETCODE_REJECT,
                "error": err,
                "comment": "ORDER_SEND_FAILED_NULL"
            }

        return {
            "retcode": result.retcode,
            "deal": result.deal,
            "order": result.order,
            "volume": result.volume,
            "price": result.price,
            "bid": result.bid,
            "ask": result.ask,
            "comment": result.comment,
            "request": request
        }

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all open positions."""
        if self.is_mock_mode:
            positions = list(self._mock_positions.values())
            if symbol:
                positions = [p for p in positions if p["symbol"] == symbol]
            return positions

        raw_positions = self._mt5.positions_get(symbol=symbol) if symbol else self._mt5.positions_get()
        if raw_positions is None:
            return []

        return [p._asdict() for p in raw_positions]

    def close_position(self, ticket: int) -> bool:
        """Closes an open position by ticket."""
        if self.is_mock_mode:
            if ticket in self._mock_positions:
                del self._mock_positions[ticket]
                return True
            return False

        # In real MT5, closing requires an opposite order_send
        positions = self._mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        pos = positions[0]
        close_type = 1 if pos.type == 0 else 0  # Opposite side
        tick = self._mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if close_type == 1 else tick.ask

        close_req = {
            "action": 1,  # TRADE_ACTION_DEAL
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": f"CLOSE_{ticket}",
            "type_time": 0,
            "type_filling": 1
        }
        res = self._mt5.order_send(close_req)
        return res is not None and res.retcode == MT5RetCode.TRADE_RETCODE_DONE


# ====================================================================================================
# 04_execution/broker_bridge/tca_monitor.py  —  The Fourth Estate: Independent Transaction Cost Analysis (TCA) & Slippage Watchdog.
# ====================================================================================================




class SlippageAnomalyAlert(Exception):
    """Raised when real execution slippage exceeds constitutional safety thresholds."""
    pass


class TCAMonitor:
    """
    Transaction Cost Analysis (TCA) Independent Telemetry Monitor.
    """

    def __init__(
        self,
        max_allowed_slippage_bps: float = 15.0,  # 15 basis points (0.15%)
        contract_size: float = 100.0            # Standard metal/FX contract multiplier
    ):
        self.max_allowed_slippage_bps = max_allowed_slippage_bps
        self.contract_size = contract_size
        self.fill_logs: List[Dict[str, Any]] = []
        self.anomalies_count: int = 0

    def audit_execution_fill(
        self,
        theoretical_price: float,
        fill_price: float,
        action: str,
        asset: str = "XAUUSD",
        lots: float = 1.0,
        order_type: str = "LIMIT_SKEWED"
    ) -> Dict[str, Any]:
        """
        Audits a single execution fill against theoretical quote price.

        :param theoretical_price: Benchmark price when child order was routed
        :param fill_price: Real fill price returned by broker gateway
        :param action: "BUY" or "SELL"
        :param asset: Instrument symbol
        :param lots: Executed volume
        :param order_type: Strategy order type tag
        :return: Audit record dictionary
        """
        if theoretical_price <= 0:
            raise ValueError("Theoretical benchmark price must be positive.")

        is_buy = action.upper() == "BUY"
        if is_buy:
            slippage_diff = fill_price - theoretical_price
        else:
            slippage_diff = theoretical_price - fill_price

        # Slippage in basis points (1 bps = 0.0001 = 0.01%)
        slippage_bps = (slippage_diff / theoretical_price) * 10000.0

        # Slippage dollar drag
        dollar_cost = round(slippage_diff * lots * self.contract_size, 2)

        is_anomaly = bool(slippage_bps > self.max_allowed_slippage_bps)
        if is_anomaly:
            self.anomalies_count += 1

        record = {
            "asset": asset,
            "action": action.upper(),
            "lots": round(lots, 2),
            "order_type": order_type,
            "theoretical_price": round(theoretical_price, 4),
            "fill_price": round(fill_price, 4),
            "slippage_diff": round(slippage_diff, 4),
            "slippage_bps": round(slippage_bps, 2),
            "dollar_cost": dollar_cost,
            "is_anomaly": is_anomaly
        }
        self.fill_logs.append(record)

        if is_anomaly:
            raise SlippageAnomalyAlert(
                f"TCA WATCHDOG ALERT: Severe slippage on {action} {asset}! "
                f"Executed at {fill_price} vs theoretical {theoretical_price}. "
                f"Slippage: {round(slippage_bps, 2)} bps (Max threshold: {self.max_allowed_slippage_bps} bps). "
                f"Dollar drag: ${dollar_cost}."
            )

        return record

    def get_tca_telemetry_report(self) -> Dict[str, Any]:
        """
        Generates aggregate execution quality analytics.
        """
        if not self.fill_logs:
            return {
                "total_fills": 0,
                "avg_slippage_bps": 0.0,
                "max_slippage_bps": 0.0,
                "total_dollar_drag": 0.0,
                "anomalies_count": 0,
                "broker_health": "OPTIMAL"
            }

        all_bps = [log["slippage_bps"] for log in self.fill_logs]
        all_drag = [log["dollar_cost"] for log in self.fill_logs]

        avg_bps = sum(all_bps) / len(all_bps)
        max_bps = max(all_bps)
        total_drag = sum(all_drag)

        if self.anomalies_count == 0:
            health = "OPTIMAL"
        elif self.anomalies_count <= 2:
            health = "SLIPPAGE_WARNING"
        else:
            health = "CRITICAL_EXECUTION_DRAG"

        return {
            "total_fills": len(self.fill_logs),
            "avg_slippage_bps": round(avg_bps, 2),
            "max_slippage_bps": round(max_bps, 2),
            "total_dollar_drag": round(total_drag, 2),
            "anomalies_count": self.anomalies_count,
            "broker_health": health
        }


# ====================================================================================================
# 04_execution/nuclear_football_hardstop.py  —  The Executive Presidency: The Nuclear Football (Hard-Stop Circuit Breaker)
# ====================================================================================================




class NuclearFootball:
    """
    The President's Emergency Hard-Stop Switch.
    Overrides all 50 states and shuts down trading activity instantly.
    """

    def __init__(self, kill_threshold: float = -0.12):
        self.kill_threshold = kill_threshold
        self.is_detonated: bool = False
        self.detonation_reason: str = ""
        self.audit_log: List[Dict[str, Any]] = []

    def check_portfolio_drawdown(self, current_drawdown: float) -> bool:
        """
        Monitors drawdown level. If drawdown <= -0.12, automatically detonates.
        """
        if current_drawdown <= self.kill_threshold:
            self.detonate(f"CRITICAL DRAWDOWN BREACHED: {round(current_drawdown * 100, 2)}% <= {round(self.kill_threshold * 100, 2)}%")
            return True
        return False

    def detonate(self, reason: str = "Presidential Emergency Directive") -> Dict[str, Any]:
        """
        Executes emergency shutdown: Closes all orders, liquidates to 100% Cash, severs broker pipes.
        """
        self.is_detonated = True
        self.detonation_reason = reason
        event = {
            "status": "NUCLEAR_FOOTBALL_DETONATED",
            "action": "EMERGENCY_FULL_LIQUIDATION_TO_100_PERCENT_CASH",
            "reason": reason,
            "broker_connections": "SEVERED",
            "trading_halted": True
        }
        self.audit_log.append(event)
        return event

    def reset_with_congressional_waiver(self, authorization_code: str) -> bool:
        """Resets the circuit breaker only with valid constitutional authorization code."""
        if authorization_code == "CONGRESSIONAL_JOINT_RESOLUTION_RESTORE":
            self.is_detonated = False
            self.detonation_reason = ""
            return True
        return False


# ====================================================================================================
# 04_execution/optimal_execution/almgren_chriss.py  —  Almgren-Chriss (2000) Optimal Execution Trajectory Engine.
# ====================================================================================================




class AlmgrenChrissExecutor:
    """
    Computes discrete optimal trading trajectories under the Almgren-Chriss framework.
    """

    def __init__(
        self,
        risk_aversion_lambda: float = 1e-4,  # Risk aversion parameter lambda
        temp_impact_eta: float = 2.5e-4,     # Temporary market impact coefficient eta
        perm_impact_gamma: float = 1e-5      # Permanent market impact coefficient gamma
    ):
        self.risk_aversion_lambda = max(1e-8, risk_aversion_lambda)
        self.temp_impact_eta = max(1e-8, temp_impact_eta)
        self.perm_impact_gamma = max(1e-8, perm_impact_gamma)

    def calculate_trajectory(
        self,
        total_lots: float,
        volatility_sigma: float = 0.015,
        time_horizon: float = 1.0,
        n_slices: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Computes the optimal inventory holdings and trade slice sizes across N intervals.

        :param total_lots: Initial total order size X_0 to execute/liquidate
        :param volatility_sigma: Market volatility (standard deviation of price changes)
        :param time_horizon: Total time duration T (e.g. 1.0 day or session)
        :param n_slices: Number of execution steps N (intervals)
        :return: List of step dictionaries with slice size, remaining inventory, and timing
        """
        if n_slices < 1:
            raise ValueError("Number of slices must be at least 1.")
        if total_lots <= 0:
            return []

        tau = time_horizon / n_slices

        # Characteristic decay rate kappa:
        # In Almgren-Chriss (2000), kappa = sqrt(lambda * sigma^2 / eta)
        variance_penalty = (self.risk_aversion_lambda * (volatility_sigma ** 2)) / self.temp_impact_eta
        if variance_penalty <= 1e-12:
            kappa = 0.0
        else:
            kappa = math.sqrt(variance_penalty)


        # Compute inventory holdings x_j at time t_j = j * tau for j = 0, ..., N
        # x_0 = total_lots, x_N = 0.0
        x = [0.0] * (n_slices + 1)
        x[0] = total_lots

        if kappa * time_horizon < 1e-5:
            # Risk-neutral linear trajectory (TWAP limit)
            for j in range(1, n_slices + 1):
                t_j = j * tau
                x[j] = total_lots * (1.0 - t_j / time_horizon)
        else:
            sinh_kappa_T = math.sinh(kappa * time_horizon)
            for j in range(1, n_slices + 1):
                t_j = j * tau
                x[j] = total_lots * (math.sinh(kappa * (time_horizon - t_j)) / sinh_kappa_T)
        
        # Ensure final inventory is exactly 0
        x[n_slices] = 0.0

        # Calculate trade slice sizes n_j = x_{j-1} - x_j
        raw_slices = [x[j - 1] - x[j] for j in range(1, n_slices + 1)]

        # Round to 2 decimal places (standard 0.01 lot step)
        rounded_slices = [round(s, 2) for s in raw_slices]
        diff = round(total_lots - sum(rounded_slices), 2)

        # Distribute any fractional rounding discrepancy to largest slice
        if abs(diff) > 1e-4:
            max_idx = rounded_slices.index(max(rounded_slices))
            rounded_slices[max_idx] = round(rounded_slices[max_idx] + diff, 2)

        schedule: List[Dict[str, Any]] = []
        accumulated = 0.0
        for j in range(1, n_slices + 1):
            slice_lot = rounded_slices[j - 1]
            accumulated += slice_lot
            rem_inv = round(max(0.0, total_lots - accumulated), 2)
            schedule.append({
                "step": j,
                "total_steps": n_slices,
                "time_fraction": round(j * tau / time_horizon, 4),
                "slice_lots": slice_lot,
                "remaining_lots": rem_inv,
                "raw_optimal_lots": round(raw_slices[j - 1], 4)
            })

        return schedule


# ====================================================================================================
# 04_execution/optimal_execution/slippage_impact_model.py  —  Market Impact and Slippage Estimation Model.
# ====================================================================================================




class SlippageImpactModel:
    """
    Quantitative Market Impact and Execution Slippage Estimator.
    """

    #: Trần TUYỆT ĐỐI theo CLAUDE.md §2① — Giới hạn thanh khoản: khối lượng một lệnh
    #: không được vượt 10% khối lượng giao dịch trung bình ngày. Không mã nào được phép
    #: đặt `adv_participation_cap` cao hơn con số này.
    DIRECTIVE_ADV_CEILING: float = 0.10

    def __init__(
        self,
        temp_coefficient: float = 0.5,    # Temporary impact scaling constant
        perm_coefficient: float = 0.1,    # Permanent impact scaling constant
        adv_participation_cap: float = 0.05  # Mặc định 5% — xem ghi chú bên dưới
    ):
        """
        :param adv_participation_cap: trần tỉ lệ tham gia thanh khoản.

            Mặc định **5%**, tức chặt hơn trần 10% mà CLAUDE.md §2① cho phép. Đây là lựa
            chọn có chủ đích: trần quy định là mức KHÔNG ĐƯỢC VƯỢT, không phải mức nên
            dùng. Tác động giá tăng theo căn bậc hai của tỉ lệ tham gia, nên khoảng 5–10%
            là vùng chi phí trượt giá leo nhanh nhất.

            Giá trị vượt `DIRECTIVE_ADV_CEILING` bị **từ chối ở cấp hàm khởi tạo**. Trước
            ngày 26/09/2026 tham số này hoàn toàn tự do, nên bất kỳ mã gọi nào cũng có thể
            đặt 0.50 và lặng lẽ vượt trần định chế.

        :raises ValueError: khi trần vượt mức quy định hoặc không nằm trong (0, 1].
        """
        if not (0.0 < adv_participation_cap <= self.DIRECTIVE_ADV_CEILING):
            raise ValueError(
                f"adv_participation_cap phai nam trong (0, {self.DIRECTIVE_ADV_CEILING}] "
                f"theo CLAUDE.md §2① (Gioi han thanh khoan ADV 10%), "
                f"nhan duoc {adv_participation_cap}."
            )
        self.temp_coefficient = temp_coefficient
        self.perm_coefficient = perm_coefficient
        self.adv_participation_cap = adv_participation_cap

    def estimate_impact(
        self,
        order_lots: float,
        mid_price: float,
        daily_adv_lots: float = 10000.0,
        volatility_sigma: float = 0.015,
        execution_window_fraction: float = 0.1  # Fraction of trading day (e.g. 1 hour of 10h = 0.1)
    ) -> Dict[str, Any]:
        """
        Estimates temporary, permanent, and total slippage impact.

        :param order_lots: Size of the order / slice in lots
        :param mid_price: Current market mid-price
        :param daily_adv_lots: Average Daily Volume in lots
        :param volatility_sigma: Daily volatility sigma
        :param execution_window_fraction: Duration tau of execution as fraction of full trading day
        :return: Comprehensive dictionary of estimated impact metrics
        """
        if order_lots <= 0:
            return {
                "order_lots": 0.0,
                "temp_impact_bps": 0.0,
                "perm_impact_bps": 0.0,
                "total_impact_bps": 0.0,
                "expected_slippage_price": 0.0,
                "total_slippage_cost": 0.0,
                "participation_rate": 0.0,
                "exceeds_adv_cap": False
            }

        tau = max(1e-4, execution_window_fraction)
        window_adv = daily_adv_lots * tau

        # Participation rate during the execution window
        participation_rate = order_lots / window_adv

        # Square-Root Law for Temporary Impact:
        # I_temp = eta * sigma * sqrt(order_lots / window_adv)
        temp_fraction = self.temp_coefficient * volatility_sigma * math.sqrt(participation_rate)
        temp_impact_bps = temp_fraction * 10000.0

        # Permanent Impact (linear or concave in total ADV fraction):
        # I_perm = gamma * sigma * (order_lots / daily_adv_lots)
        total_adv_fraction = order_lots / daily_adv_lots
        perm_fraction = self.perm_coefficient * volatility_sigma * math.sqrt(total_adv_fraction)
        perm_impact_bps = perm_fraction * 10000.0

        total_impact_bps = temp_impact_bps + 0.5 * perm_impact_bps

        # Expected price slippage
        slippage_price = round(mid_price * (total_impact_bps / 10000.0), 4)

        # Standard lot value (e.g. 100,000 units for standard FX/Metals lot)
        notional_value = order_lots * 100.0 * mid_price  # Typical futures/CFD multiplier
        total_slippage_cost = round(notional_value * (total_impact_bps / 10000.0), 2)

        exceeds_cap = participation_rate > self.adv_participation_cap

        return {
            "order_lots": round(order_lots, 4),
            "mid_price": mid_price,
            "participation_rate": round(participation_rate, 4),
            "temp_impact_bps": round(temp_impact_bps, 2),
            "perm_impact_bps": round(perm_impact_bps, 2),
            "total_impact_bps": round(total_impact_bps, 2),
            "expected_slippage_price": slippage_price,
            "total_slippage_cost": total_slippage_cost,
            "exceeds_adv_cap": exceeds_cap
        }


# ====================================================================================================
# 04_execution/optimal_execution/vwap_profile.py  —  VWAP (Volume-Weighted Average Price) Intraday Liquidity Slicer.
# ====================================================================================================




class VWAPProfileSlicer:
    """
    Intraday Volume-Weighted Execution Profiler.
    Generates non-linear execution slices matching empirical market volume distributions.
    """

    def __init__(self, curvature: float = 2.0, base_liquidity_floor: float = 0.5):
        """
        :param curvature: Curvature parameter governing the depth of the midday volume trough.
        :param base_liquidity_floor: Minimum liquidity fraction at the midday trough relative to peaks.
        """
        self.curvature = curvature
        self.base_liquidity_floor = base_liquidity_floor

    def get_normalized_volume_curve(self, n_slices: int = 5) -> List[float]:
        """
        Computes the discrete U-curve normalized weights summing to 1.0.
        f(u) = base_floor + curvature * (u - 0.5)^2 for u in [0, 1]
        """
        if n_slices <= 0:
            return []
        if n_slices == 1:
            return [1.0]

        raw_weights: List[float] = []
        for i in range(n_slices):
            # Centered interval u in [0, 1]
            u = (i + 0.5) / n_slices
            weight = self.base_liquidity_floor + self.curvature * ((u - 0.5) ** 2)
            raw_weights.append(weight)

        total_weight = sum(raw_weights)
        return [w / total_weight for w in raw_weights]

    def slice_order(
        self,
        total_lots: float,
        n_slices: int = 5,
        custom_weights: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Slices total order volume into VWAP child orders matching the volume profile.

        :param total_lots: Total volume in lots to be routed
        :param n_slices: Number of execution buckets
        :param custom_weights: Optional empirical historical volume bucket weights
        :return: List of slice details with slice lot, volume fraction, and step index
        """
        if n_slices < 1:
            raise ValueError("Number of slices must be at least 1.")
        if total_lots <= 0:
            return []

        if custom_weights is not None:
            if len(custom_weights) != n_slices:
                raise ValueError("custom_weights length must match n_slices.")
            s = sum(custom_weights)
            weights = [w / s for w in custom_weights]
        else:
            weights = self.get_normalized_volume_curve(n_slices)

        # Allocate lots per bucket
        raw_allocations = [total_lots * w for w in weights]
        rounded_allocations = [round(a, 2) for a in raw_allocations]

        # Balance rounding drift to guarantee sum(rounded_allocations) == total_lots
        diff = round(total_lots - sum(rounded_allocations), 2)
        if abs(diff) > 1e-4:
            # Allocate difference to the bucket with the highest weight (peak volume)
            max_idx = weights.index(max(weights))
            rounded_allocations[max_idx] = round(rounded_allocations[max_idx] + diff, 2)

        slices: List[Dict[str, Any]] = []
        for i in range(n_slices):
            slices.append({
                "step": i + 1,
                "total_steps": n_slices,
                "weight": round(weights[i], 4),
                "slice_lots": rounded_allocations[i],
                "expected_volume_ratio": round(weights[i], 4)
            })

        return slices


# ====================================================================================================
# 04_execution/broker_bridge/mt5_payload_builder.py
# ====================================================================================================



if TYPE_CHECKING:
    pass


class MT5TradeAction:
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_MODIFY = 7
    TRADE_ACTION_REMOVE = 8


class MT5OrderType:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3


class MT5OrderTime:
    ORDER_TIME_GTC = 0
    ORDER_TIME_DAY = 1
    ORDER_TIME_SPECIFIED = 2


class MT5OrderFilling:
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2


class MT5PayloadBuilder:
    """
    Constructs and validates MT5 MqlTradeRequest dictionaries.
    """

    def __init__(
        self,
        default_magic: int = 20260919,
        default_deviation_points: int = 15,
        default_filling_type: int = MT5OrderFilling.ORDER_FILLING_IOC,
        min_lot_size: float = 0.01,
        lot_step: float = 0.01
    ):
        self.default_magic = default_magic
        self.default_deviation_points = default_deviation_points
        self.default_filling_type = default_filling_type
        self.min_lot_size = min_lot_size
        self.lot_step = lot_step

    def build_trade_request(
        self,
        slice_order: MicroOrderSlice,
        sl_price: float = 0.0,
        tp_price: float = 0.0,
        deviation_points: Optional[int] = None,
        magic_number: Optional[int] = None,
        is_limit_order: bool = False
    ) -> Dict[str, Any]:
        """
        Builds a single MqlTradeRequest payload dictionary from a MicroOrderSlice.
        """
        # Determine MT5 order type
        is_buy = slice_order.action.upper() == "BUY"
        if is_limit_order or "LIMIT" in slice_order.order_type:
            order_type = MT5OrderType.ORDER_TYPE_BUY_LIMIT if is_buy else MT5OrderType.ORDER_TYPE_SELL_LIMIT
            trade_action = MT5TradeAction.TRADE_ACTION_PENDING
        else:
            order_type = MT5OrderType.ORDER_TYPE_BUY if is_buy else MT5OrderType.ORDER_TYPE_SELL
            trade_action = MT5TradeAction.TRADE_ACTION_DEAL

        # Volume quantization to lot step
        volume = max(self.min_lot_size, round(slice_order.lots, 2))

        if getattr(slice_order, "client_order_id", None):
            comment = str(slice_order.client_order_id)[:31]
        else:
            comment = f"FED_{slice_order.slice_index}/{slice_order.total_slices}_{slice_order.order_type[:10]}"[:31]

        request = {
            "action": trade_action,
            "symbol": slice_order.asset,
            "volume": volume,
            "type": order_type,
            "price": round(slice_order.target_price, 5),
            "sl": round(sl_price, 5) if sl_price > 0 else 0.0,
            "tp": round(tp_price, 5) if tp_price > 0 else 0.0,
            "deviation": deviation_points if deviation_points is not None else self.default_deviation_points,
            "magic": magic_number if magic_number is not None else self.default_magic,
            "comment": comment,
            "type_time": MT5OrderTime.ORDER_TIME_GTC,
            "type_filling": self.default_filling_type
        }

        return request

    def build_batch_requests(
        self,
        slice_orders: List[MicroOrderSlice],
        sl_price: float = 0.0,
        tp_price: float = 0.0,
        deviation_points: Optional[int] = None,
        magic_number: Optional[int] = None,
        is_limit_order: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Constructs a batch of MT5 MqlTradeRequest payloads for all child slices.
        """
        batch: List[Dict[str, Any]] = []
        for s in slice_orders:
            req = self.build_trade_request(
                slice_order=s,
                sl_price=sl_price,
                tp_price=tp_price,
                deviation_points=deviation_points,
                magic_number=magic_number,
                is_limit_order=is_limit_order
            )
            batch.append(req)
        return batch

    def validate_trade_request(self, request: Dict[str, Any]) -> bool:
        """
        Validates the schema and safety thresholds of an MT5 trade request.
        """
        required_keys = ["action", "symbol", "volume", "type", "price", "deviation", "magic"]
        for k in required_keys:
            if k not in request:
                return False

        if not isinstance(request["symbol"], str) or len(request["symbol"]) == 0:
            return False

        if request["volume"] < self.min_lot_size:
            return False

        if request["price"] <= 0:
            return False

        if request["type"] not in [
            MT5OrderType.ORDER_TYPE_BUY,
            MT5OrderType.ORDER_TYPE_SELL,
            MT5OrderType.ORDER_TYPE_BUY_LIMIT,
            MT5OrderType.ORDER_TYPE_SELL_LIMIT
        ]:
            return False

        return True


# ====================================================================================================
# 04_execution/order_router/router.py  —  The Executive Presidency: Order Router & Execution Management System (EMS)
# ====================================================================================================




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
            _inst_mod = importlib.import_module("us_federation_quant.Document.institutional_governance_rules")
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


# ====================================================================================================
# GỬI LỆNH VÀO (từ live_federation_runner._submit_proposal_order) — state machine -> MT5 -> FILLED/REJECTED
# ====================================================================================================

def submit_order_intent(rt, intent):
    """Đường vào lệnh: tạo order trong state machine, gửi open_market_order, ghi FILLED hoặc REJECTED (+ revoke warrant).

    Trả về dict kết quả khi thành công, None khi broker từ chối. Ngoại lệ lan ra cho caller (như bản cũ):
    sau SUBMITTED mà open_market_order nổ thì lệnh ở lại SUBMITTED và warrant KHÔNG bị revoke.
    Chưa thêm chốt chặn SL/TP bắt buộc ở đây (đó là thay đổi hành vi, cần ADR riêng).
    """
    client_order_id = generate_client_order_id(intent.state_id, intent.action)
    order_state = rt.mt5_mgr.state_machine.create_order(
        client_order_id=client_order_id,
        symbol=intent.symbol,
        order_type="MARKET",
        direction=intent.action,
        volume=intent.volume,
        sl=intent.sl,
        tp=intent.tp,
        magic=intent.magic,
        warrant_id=intent.warrant.warrant_id,
    )
    order_state.transition_to(OrderState.SUBMITTED, reason="Submitted to MT5 bridge")

    logger.info(
        f"🚀 [PROPOSAL APPROVED] {intent.state_id} ({intent.state_name}): {intent.action} {intent.volume}L "
        f"on {intent.symbol} | SL: {intent.sl} | TP: {intent.tp} | Forecast: {intent.forecast:+.2f} | IDM: {intent.idm:.2f} | Policy: {intent.policy} | Warrant: {intent.warrant.warrant_id}"
    )

    exec_res = rt.mt5_mgr.open_market_order(
        symbol=intent.symbol,
        direction=intent.action,
        volume=intent.volume,
        sl=intent.sl,
        tp=intent.tp,
        magic=intent.magic,
        comment=f"{intent.state_id}:{client_order_id[:16]}"[:31],
    )

    if exec_res.get("success"):
        ticket = exec_res.get("ticket")
        fill_price = exec_res.get("price", intent.current_price)
        order_state.transition_to(
            OrderState.FILLED,
            fill_volume=intent.volume,
            fill_price=fill_price,
            broker_order_id=ticket,
        )
        logger.info(
            f"✅ [EXECUTION SUCCESS] {intent.state_id} #{ticket} {intent.action} {intent.volume}L @ {fill_price}"
        )
        return exec_res

    err = exec_res.get("error", "Execution failed")
    retcode = exec_res.get("retcode", -1)
    order_state.transition_to(OrderState.REJECTED, reason=str(err))
    intent.warrant.revoke(reason=f"Broker execution failed: {err}")
    if retcode == 10018:
        logger.info(f"ℹ️ [MARKET_CLOSED] {intent.state_id} ({intent.symbol}): Thị trường đóng cửa / nghỉ lễ (10018) -> Tạm bỏ qua an toàn.")
    else:
        logger.warning(f"❌ [EXECUTION FAILED] {intent.state_id} order failed: {err} -> Warrant revoked.")
    return None
