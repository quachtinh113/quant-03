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
        self._initialized = True

    def connect(self) -> bool:
        """Initialize and login to MetaTrader 5."""
        if not MT5_AVAILABLE:
            logger.error("❌ MetaTrader5 Python library is not installed.")
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

            # Try initial connection
            init_ok = mt5.initialize(**init_kwargs)
            if not init_ok and ("login" in init_kwargs or "password" in init_kwargs):
                # If terminal is already running and logged in, path-only initialize succeeds reliably
                fallback_kwargs = {"timeout": 30000}
                if "path" in init_kwargs:
                    fallback_kwargs["path"] = init_kwargs["path"]
                init_ok = mt5.initialize(**fallback_kwargs)

            if not init_ok:
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
                    curr_acc_after = mt5.account_info()
                    if curr_acc_after and curr_acc_after.login == self.account:
                        login_ok = True
                    else:
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

            # Quick retry if MT5 IPC socket had a transient idle pause
            time.sleep(0.3)
            term_info_retry = mt5.terminal_info()
            if term_info_retry and term_info_retry.connected:
                self.connected = True
                return True

            # Secondary account_info check to verify active session
            acct_info = mt5.account_info()
            if acct_info is not None and (not self.account or acct_info.login == self.account):
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

    def get_rates(self, symbol: str, timeframe_str: str, count: int = 100) -> Optional[pd.DataFrame]:
        """Fetch latest candles for a symbol. Returns DataFrame with UTC datetime index."""
        if not self.ensure_connected():
            return None

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

        actual_symbol = self.resolve_symbol(symbol)
        with self._lock:
            tick = mt5.symbol_info_tick(actual_symbol)
            if not tick:
                return None
            return {
                "symbol": actual_symbol,
                "bid": float(tick.bid),
                "ask": float(tick.ask),
                "spread": float(tick.ask - tick.bid),
                "time": tick.time,
            }

    def resolve_symbol(self, symbol: str) -> str:
        """Resolve valid MT5 symbol on active broker (e.g. XAUUSD vs XAUUSDm)."""
        if not MT5_AVAILABLE:
            return symbol

        info = mt5.symbol_info(symbol)
        if info is not None:
            mt5.symbol_select(symbol, True)
            return symbol

        if symbol.endswith("m"):
            base_sym = symbol[:-1]
            info = mt5.symbol_info(base_sym)
            if info is not None:
                mt5.symbol_select(base_sym, True)
                return base_sym

        m_sym = f"{symbol}m"
        info = mt5.symbol_info(m_sym)
        if info is not None:
            mt5.symbol_select(m_sym, True)
            return m_sym

        return symbol

    def get_symbol_spec(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieve instrument specifications (point, digits, contract_size, lot steps)."""
        if not self.ensure_connected():
            return None

        actual_symbol = self.resolve_symbol(symbol)
        with self._lock:
            info = mt5.symbol_info(actual_symbol)
            if not info:
                return None
            return {
                "symbol": actual_symbol,
                "point": float(info.point),
                "digits": int(info.digits),
                "contract_size": float(info.trade_contract_size),
                "volume_min": float(info.volume_min),
                "volume_max": float(info.volume_max),
                "volume_step": float(info.volume_step),
                "spread_points": int(info.spread),
                "filling_mode": int(info.filling_mode) if hasattr(info, "filling_mode") else 0,
            }

    def _determine_filling_mode(self, symbol_spec: Dict[str, Any]) -> int:
        """Select appropriate MT5 filling mode based on symbol capabilities."""
        fm_mask = symbol_spec.get("filling_mode", 0)
        if fm_mask & 1:
            return mt5.ORDER_FILLING_FOK
        if fm_mask & 2:
            return mt5.ORDER_FILLING_IOC
        if fm_mask & 4:
            return mt5.ORDER_FILLING_RETURN
        return mt5.ORDER_FILLING_FOK

    def normalize_lot(self, symbol: str, lot: float) -> float:
        """Round volume down to the instrument's volume_step and clamp between min and max."""
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

        actual_symbol = self.resolve_symbol(symbol) if symbol else None
        with self._lock:
            raw = mt5.positions_get()
            if raw is None:
                return []

            positions = []
            for p in raw:
                if magic is not None and p.magic != magic:
                    continue
                if actual_symbol is not None and p.symbol != actual_symbol:
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
        comment: str = ""
    ) -> Dict[str, Any]:
        """Send an IOC/FOK market order to MT5."""
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to MT5"}

        actual_symbol = self.resolve_symbol(symbol)
        spec = self.get_symbol_spec(actual_symbol)
        if not spec:
            return {"success": False, "error": f"Invalid symbol {symbol}"}

        lot = self.normalize_lot(actual_symbol, volume)
        tick = self.get_tick(actual_symbol)
        if not tick:
            return {"success": False, "error": f"Failed to get tick for {actual_symbol}"}

        order_type = mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick["ask"] if direction.upper() == "BUY" else tick["bid"]
        primary_filling = self._determine_filling_mode(spec)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": actual_symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": round(sl, spec["digits"]) if sl > 0 else 0.0,
            "tp": round(tp, spec["digits"]) if tp > 0 else 0.0,
            "deviation": 20,
            "magic": magic,
            "comment": str(comment)[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": primary_filling,
        }

        with self._lock:
            result = mt5.order_send(request)
            # Try alternate filling mode if retcode 10030 (Unsupported filling mode)
            if not result or result.retcode == 10030:
                alt_fillings = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
                for alt_f in alt_fillings:
                    if alt_f == primary_filling:
                        continue
                    request["type_filling"] = alt_f
                    result = mt5.order_send(request)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        break

            if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = result.comment if result else str(mt5.last_error())
                retcode = result.retcode if result else -1
                logger.error(f"❌ Order Send Failed ({actual_symbol} {direction} {lot}L, magic={magic}): {err_msg} (retcode={retcode})")
                return {"success": False, "error": err_msg, "retcode": retcode}

            logger.info(
                f"🚀 ORDER EXECUTED: Ticket #{result.order} | {actual_symbol} {direction} {lot}L @ {result.price} | Magic: {magic}"
            )
            return {
                "success": True,
                "ticket": result.order,
                "price": result.price,
                "volume": result.volume,
                "magic": magic
            }

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
            spec = self.get_symbol_spec(pos.symbol)
            primary_filling = self._determine_filling_mode(spec) if spec else mt5.ORDER_FILLING_FOK

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
                "type_filling": primary_filling,
            }

            result = mt5.order_send(request)
            if not result or result.retcode == 10030:
                alt_fillings = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
                for alt_f in alt_fillings:
                    if alt_f == primary_filling:
                        continue
                    request["type_filling"] = alt_f
                    result = mt5.order_send(request)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        break

            if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = result.comment if result else str(mt5.last_error())
                logger.error(f"❌ Close Failed #{ticket}: {err_msg}")
                return {"success": False, "error": err_msg}

            logger.info(f"✅ POSITION CLOSED: Ticket #{ticket} ({pos.symbol} {pos.volume}L, Profit: ${pos.profit:.2f})")
            return {"success": True, "ticket": ticket, "profit": pos.profit}

    def modify_position_sltp(self, ticket: int, sl: float, tp: float = 0.0) -> Dict[str, Any]:
        """Modify Stop Loss and Take Profit for an open position (Article 00 Compliance)."""
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to MT5"}

        with self._lock:
            positions = mt5.positions_get(ticket=ticket)
            if not positions or len(positions) == 0:
                return {"success": False, "error": f"Position #{ticket} not found"}

            pos = positions[0]
            spec = self.get_symbol_spec(pos.symbol)
            digits = spec.get("digits", 2) if spec else 2

            sl_price = round(sl, digits) if sl > 0 else 0.0
            tp_price = round(tp, digits) if tp > 0 else 0.0

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "sl": sl_price,
                "tp": tp_price,
            }

            result = mt5.order_send(request)
            if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = result.comment if result else str(mt5.last_error())
                logger.error(f"❌ SL/TP Modification Failed #{ticket}: {err_msg}")
                return {"success": False, "error": err_msg}

            logger.info(f"🛡️ POSITION SL/TP PROTECTED: Ticket #{ticket} ({pos.symbol}) -> SL: {sl_price}, TP: {tp_price}")
            return {"success": True, "ticket": ticket, "sl": sl_price, "tp": tp_price}

    def enforce_mandatory_sl_protection(self, default_sl_pct: float = 0.015) -> List[Dict[str, Any]]:
        """Scans open positions and attaches mandatory SL if missing (Article 00 Safeguard)."""
        positions = self.get_positions()
        protected = []
        for p in positions:
            if p["sl"] <= 0.0:
                spec = self.get_symbol_spec(p["symbol"])
                price = p["price_open"]
                digits = spec.get("digits", 2) if spec else 2

                if p["type"] == "BUY":
                    sl_calculated = price * (1.0 - default_sl_pct)
                else:
                    sl_calculated = price * (1.0 + default_sl_pct)

                res = self.modify_position_sltp(ticket=p["ticket"], sl=round(sl_calculated, digits))
                if res.get("success"):
                    protected.append(res)
        return protected

    def shutdown(self):
        """Cleanly shutdown MT5 connection."""
        with self._lock:
            if MT5_AVAILABLE and self.connected:
                mt5.shutdown()
                self.connected = False
                logger.info("🔌 MT5 connection shut down cleanly.")
