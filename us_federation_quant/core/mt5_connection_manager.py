"""
US Federation Quant — MT5 Connection Manager
Central singleton connector for MetaTrader 5 on the local workstation.
Handles connection health, auto-reconnection, data feeds, and order routing.
"""

import os
import time
import math
import logging
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import pandas as pd

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

try:
    from us_federation_quant.core.audit_logger import get_logger
except ImportError:
    try:
        from core.audit_logger import get_logger
    except ImportError:
        def get_logger():
            return logging.getLogger("USFederationQuant")

logger = get_logger()

try:
    from us_federation_quant.core.order_state_machine import (
        OrderReconciliationManager,
        OrderState,
        FederationOrder,
        DuplicateOrderSubmissionError,
        generate_client_order_id,
    )
except ImportError:
    from core.order_state_machine import (
        OrderReconciliationManager,
        OrderState,
        FederationOrder,
        DuplicateOrderSubmissionError,
        generate_client_order_id,
    )

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
            logger.error("❌ MetaTrader5 Python library is not installed.")
            return False

        with self._lock:
            try:
                mt5.shutdown()
            except Exception:
                pass
            init_kwargs = {"timeout": 30000}
            if self.terminal_path and os.path.exists(self.terminal_path):
                init_kwargs["path"] = self.terminal_path
            if self.account:
                init_kwargs["login"] = int(self.account)
            if self.password:
                init_kwargs["password"] = str(self.password)
            if self.server:
                init_kwargs["server"] = str(self.server)

            if not mt5.initialize(**init_kwargs):
                err = mt5.last_error()
                logger.error(f"❌ MT5 initialize() failed: {err}")
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
                    logger.error(f"❌ MT5 login({self.account} @ {self.server}) failed: {err}")
                    self.connected = False
                    return False

            term_info = mt5.terminal_info()
            acct_info = mt5.account_info()
            if not term_info or not acct_info:
                logger.warning("⚠️ MT5 initialized but terminal_info / account_info unavailable.")
                self.connected = False
                return False

            self.connected = True
            logger.info(
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

        logger.warning("⚠️ MT5 connection dropped. Attempting reconnect...")
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

            # Check if trading is explicitly disabled (trade_mode == 0)
            if hasattr(info, "trade_mode") and info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                return False

            tick = mt5.symbol_info_tick(symbol) if MT5_AVAILABLE else None
            if not tick or tick.time == 0:
                return False

            now_ts = datetime.now(timezone.utc).timestamp()
            tick_age = now_ts - tick.time
            if tick_age > max_tick_age_seconds:
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
                logger.error(f"❌ Cannot select symbol '{symbol}' in Market Watch.")
                return None

            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None or len(rates) == 0:
                logger.error(f"❌ Failed to fetch rates for {symbol} ({timeframe_str}): {mt5.last_error()}")
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
            logger.warning(f"⚠️ [IDEMPOTENCY] Duplicate order submission prevented: {e}")
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
                logger.error(f"❌ Order Send Failed ({symbol} {direction} {lot}L, magic={magic}, cid={cid}): {err_msg} (retcode={retcode})")
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

            logger.info(
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

    def close_position(self, ticket: int) -> Dict[str, Any]:
        """Close an open position by ticket using an opposite deal."""
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
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": price,
                "deviation": 20,
                "magic": pos.magic,
                "comment": "Fleet Close",
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
                logger.error(f"❌ Close Failed #{ticket}: {err_msg}")
                return {"success": False, "error": err_msg}

            logger.info(f"✅ POSITION CLOSED: Ticket #{ticket} ({pos.symbol} {pos.volume}L, Profit: ${pos.profit:.2f})")
            return {"success": True, "ticket": ticket, "profit": pos.profit}

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
                    logger.info(f"🛡️ [MANDATORY SL ASSIGNED] Ticket #{ticket} ({symbol} {pos_type}) assigned SL={calc_sl}")
                    modified.append(res)

        return modified

    def shutdown(self):
        """Cleanly shutdown MT5 connection."""
        with self._lock:
            if MT5_AVAILABLE and self.connected:
                mt5.shutdown()
                self.connected = False
                logger.info("🔌 MT5 connection shut down cleanly.")
